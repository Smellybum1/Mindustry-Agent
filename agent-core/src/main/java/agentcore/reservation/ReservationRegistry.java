package agentcore.reservation;

import agentcore.AgentId;

import java.util.ArrayList;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * The soft-reservation registry for tiles, resources, and regions (brief §11.6,
 * §23.5). Reservations are tied to task lifecycle: acquire on demand, and the
 * board releases them all with {@link #releaseAll(String)} when the owning task
 * terminates or reopens.
 *
 * <p>Conflict rules:
 * <ul>
 *   <li><b>Human override</b> — a human reservation always wins. Acquiring a
 *       human reservation over overlapping agent reservations makes those agents
 *       yield (they are removed and a {@link ReservationConflict} is recorded);
 *       acquiring an agent reservation over a human one is rejected.</li>
 *   <li><b>Agent vs agent</b> — incompatible overlap between different tasks is
 *       rejected. Same-task re-reservation is always compatible (idempotent
 *       extension).</li>
 *   <li><b>Resource budget</b> — if a per-item capacity is configured, an agent
 *       acquisition that would push total reserved above capacity is rejected;
 *       human reservations are always granted and consume the budget first.</li>
 * </ul>
 *
 * <p>Invariant (brief §23.5): total reserved amount per item never goes negative,
 * and releasing only ever removes existing reservations. Deterministic iteration
 * order (insertion order); single-threaded by contract, not synchronized.
 */
public final class ReservationRegistry{
    private final List<TileReservation> tiles = new ArrayList<>();
    private final List<ResourceReservation> resources = new ArrayList<>();
    private final List<RegionReservation> regions = new ArrayList<>();
    private final Map<String, Integer> capacity = new LinkedHashMap<>();

    private final List<ReservationConflict> conflictLog = new ArrayList<>();

    /** Configure a resource budget for {@code item}; agents cannot reserve beyond it. */
    public void setCapacity(String item, int amount){
        if(amount < 0) throw new IllegalArgumentException("capacity must be non-negative");
        capacity.put(item, amount);
    }

    // ---- tiles ----

    /** Attempt to reserve a rectangle of tiles for a task. */
    public ReservationOutcome acquireTile(String taskId, AgentId agent, Rect area, boolean human, long tick){
        List<Reservation> yielded = new ArrayList<>();
        for(TileReservation e : tiles){
            if(e.taskId().equals(taskId)) continue;           // same task: compatible
            if(!e.area().overlaps(area)) continue;            // disjoint: compatible
            ReservationOutcome decision = resolve(e, taskId, agent, human, tick,
                "tile " + area, yielded);
            if(decision != null) return decision;             // rejected
        }
        // Any agent reservations that must yield to a human have been collected.
        List<ReservationConflict> conflicts = commitYields(yielded, taskId, agent, human, tick, "tile " + area);
        tiles.add(new TileReservation(taskId, agent, area, human));
        return conflicts.isEmpty() ? ReservationOutcome.ofGranted() : ReservationOutcome.ofHumanOverride(conflicts);
    }

    /** All tile reservations overlapping {@code area}, unmodifiable. */
    public List<TileReservation> tileOverlaps(Rect area){
        List<TileReservation> out = new ArrayList<>();
        for(TileReservation e : tiles){
            if(e.area().overlaps(area)) out.add(e);
        }
        return Collections.unmodifiableList(out);
    }

    /** Active tile reservations in deterministic acquisition order. */
    public List<TileReservation> tileReservations(){
        return Collections.unmodifiableList(tiles);
    }

    // ---- resources ----

    /** Attempt to reserve {@code amount} of {@code item} for a task. */
    public ReservationOutcome acquireResource(String taskId, AgentId agent, String item, int amount, boolean human, long tick){
        if(amount < 0) throw new IllegalArgumentException("amount must be non-negative");
        if(!human && capacity.containsKey(item)){
            int cap = capacity.get(item);
            if(reservedAmount(item) + amount > cap){
                ReservationConflict c = new ReservationConflict(tick, taskId, agent, item, agent, false,
                    "resource budget exceeded: " + item + " reserved " + reservedAmount(item) + "/" + cap
                        + ", requested " + amount);
                conflictLog.add(c);
                return ReservationOutcome.ofRejected(ReservationResult.REJECTED_CAPACITY, c);
            }
        }
        List<ReservationConflict> conflicts = human
            ? yieldResourcesForHuman(taskId, agent, item, amount, tick)
            : List.of();
        resources.add(new ResourceReservation(taskId, agent, item, amount, human));
        return conflicts.isEmpty() ? ReservationOutcome.ofGranted()
            : ReservationOutcome.ofHumanOverride(conflicts);
    }

    /** Total amount of {@code item} currently reserved (always &ge; 0). */
    public int reservedAmount(String item){
        int total = 0;
        for(ResourceReservation r : resources){
            if(r.item().equals(item)) total += r.amount();
        }
        return total;
    }

    /** Reserved amount filtered by human/agent ownership. */
    public int reservedAmount(String item, boolean human){
        int total = 0;
        for(ResourceReservation r : resources){
            if(r.item().equals(item) && r.human() == human) total += r.amount();
        }
        return total;
    }

    /** Whether an agent could reserve this amount under the current human resource floor. */
    public boolean canAgentReserve(String item, int amount){
        if(amount < 0) throw new IllegalArgumentException("amount must be non-negative");
        return !capacity.containsKey(item) || reservedAmount(item) + amount <= capacity.get(item);
    }

    /**
     * Yield newest agent resource tasks until the live stock can preserve every
     * active human reservation. Human demand may itself exceed stock, but agent
     * work is never allowed to make that deficit worse.
     */
    public ReservationOutcome enforceHumanFloor(
        String winnerTaskId,
        AgentId winnerAgent,
        String item,
        int available,
        long tick
    ){
        if(available < 0) throw new IllegalArgumentException("available must be non-negative");
        List<ReservationConflict> conflicts = yieldAgentResourceTasks(winnerTaskId,
            winnerAgent, item, reservedAmount(item), available, tick);
        return conflicts.isEmpty() ? ReservationOutcome.ofGranted()
            : ReservationOutcome.ofHumanOverride(conflicts);
    }

    /** Active resource reservations in deterministic acquisition order. */
    public List<ResourceReservation> resourceReservations(){
        return Collections.unmodifiableList(resources);
    }

    // ---- regions ----

    /** Attempt to reserve a named region of responsibility for a task. */
    public ReservationOutcome acquireRegion(String taskId, AgentId agent, String regionId, boolean human, long tick){
        List<Reservation> yielded = new ArrayList<>();
        for(RegionReservation e : regions){
            if(e.taskId().equals(taskId)) continue;
            if(!e.regionId().equals(regionId)) continue;
            ReservationOutcome decision = resolve(e, taskId, agent, human, tick,
                "region " + regionId, yielded);
            if(decision != null) return decision;
        }
        List<ReservationConflict> conflicts = commitYields(yielded, taskId, agent, human, tick, "region " + regionId);
        regions.add(new RegionReservation(taskId, agent, regionId, human));
        return conflicts.isEmpty() ? ReservationOutcome.ofGranted() : ReservationOutcome.ofHumanOverride(conflicts);
    }

    /** True if {@code regionId} is reserved by any task. */
    public boolean isRegionReserved(String regionId){
        for(RegionReservation r : regions){
            if(r.regionId().equals(regionId)) return true;
        }
        return false;
    }

    /** Active region reservations in deterministic acquisition order. */
    public List<RegionReservation> regionReservations(){
        return Collections.unmodifiableList(regions);
    }

    /** Number of active reservations of every kind owned by {@code taskId}. */
    public int countForTask(String taskId){
        int count = 0;
        for(TileReservation reservation : tiles) if(reservation.taskId().equals(taskId)) count++;
        for(ResourceReservation reservation : resources) if(reservation.taskId().equals(taskId)) count++;
        for(RegionReservation reservation : regions) if(reservation.taskId().equals(taskId)) count++;
        return count;
    }

    // ---- lifecycle ----

    /** Release every reservation owned by {@code taskId}; returns how many were removed. */
    public int releaseAll(String taskId){
        int before = tiles.size() + resources.size() + regions.size();
        tiles.removeIf(r -> r.taskId().equals(taskId));
        resources.removeIf(r -> r.taskId().equals(taskId));
        regions.removeIf(r -> r.taskId().equals(taskId));
        return before - (tiles.size() + resources.size() + regions.size());
    }

    /** Total number of active reservations across all kinds. */
    public int size(){
        return tiles.size() + resources.size() + regions.size();
    }

    /** Drain the conflict log (agent yields and rejections) since the last drain. */
    public List<ReservationConflict> drainConflicts(){
        List<ReservationConflict> out = new ArrayList<>(conflictLog);
        conflictLog.clear();
        return out;
    }

    /** Clear all reservations, capacities, and conflicts (episode reset). */
    public void reset(){
        tiles.clear();
        resources.clear();
        regions.clear();
        capacity.clear();
        conflictLog.clear();
    }

    // ---- shared conflict resolution for tiles/regions ----

    /**
     * Decide a single overlap between an incompatible existing reservation and a
     * pending acquisition. Returns a rejection outcome to abort the acquisition,
     * or {@code null} to continue (adding {@code existing} to {@code yielded} when
     * it must yield to a human).
     */
    private ReservationOutcome resolve(Reservation existing, String taskId, AgentId agent, boolean human,
                                       long tick, String what, List<Reservation> yielded){
        if(existing.human() && !human){
            // Human holds it: the agent must yield.
            ReservationConflict c = new ReservationConflict(tick, taskId, agent,
                existing.taskId(), existing.agent(), true,
                "yield to human reservation on " + what);
            conflictLog.add(c);
            return ReservationOutcome.ofRejected(ReservationResult.REJECTED_HUMAN_PRIORITY, c);
        }
        if(human && !existing.human()){
            // Incoming human overrides this agent reservation.
            yielded.add(existing);
            return null;
        }
        if(!human && !existing.human()){
            // Agent vs agent: incompatible.
            ReservationConflict c = new ReservationConflict(tick, taskId, agent,
                existing.taskId(), existing.agent(), false,
                "incompatible overlap on " + what);
            conflictLog.add(c);
            return ReservationOutcome.ofRejected(ReservationResult.REJECTED_OVERLAP, c);
        }
        // human vs human: compatible, humans coordinate among themselves.
        return null;
    }

    private List<ReservationConflict> commitYields(List<Reservation> yielded, String winnerTaskId, AgentId winnerAgent,
                                                   boolean winnerHuman, long tick, String what){
        if(yielded.isEmpty()) return List.of();
        LinkedHashMap<String, Reservation> yieldedTasks = new LinkedHashMap<>();
        for(Reservation e : yielded){
            if(e instanceof TileReservation tile){
                tiles.remove(tile);
            }else if(e instanceof RegionReservation region){
                regions.remove(region);
            }else{
                throw new IllegalStateException("only tile and region reservations may yield");
            }
            yieldedTasks.putIfAbsent(e.taskId(), e);
        }
        List<ReservationConflict> conflicts = new ArrayList<>();
        for(Reservation e : yieldedTasks.values()){
            ReservationConflict c = new ReservationConflict(tick, e.taskId(), e.agent(),
                winnerTaskId, winnerAgent, winnerHuman, "agent reservation yielded to human on " + what);
            conflicts.add(c);
            conflictLog.add(c);
        }
        return conflicts;
    }

    private List<ReservationConflict> yieldResourcesForHuman(
        String taskId,
        AgentId agent,
        String item,
        int amount,
        long tick
    ){
        Integer cap = capacity.get(item);
        if(cap == null || reservedAmount(item) + amount <= cap) return List.of();
        return yieldAgentResourceTasks(taskId, agent, item,
            reservedAmount(item) + amount, cap, tick);
    }

    private List<ReservationConflict> yieldAgentResourceTasks(
        String taskId,
        AgentId agent,
        String item,
        int projected,
        int limit,
        long tick
    ){
        LinkedHashMap<String, ResourceReservation> yieldedTasks = new LinkedHashMap<>();
        for(int i = resources.size() - 1; i >= 0 && projected > limit; i--){
            ResourceReservation reservation = resources.get(i);
            if(reservation.human() || !reservation.item().equals(item)
                || reservation.taskId().equals(taskId)
                || yieldedTasks.containsKey(reservation.taskId())) continue;
            yieldedTasks.put(reservation.taskId(), reservation);
            for(ResourceReservation candidate : resources){
                if(candidate.taskId().equals(reservation.taskId())
                    && candidate.item().equals(item)) projected -= candidate.amount();
            }
        }
        ArrayList<ReservationConflict> conflicts = new ArrayList<>();
        for(ResourceReservation yielded : yieldedTasks.values()){
            releaseAll(yielded.taskId());
            ReservationConflict conflict = new ReservationConflict(tick, yielded.taskId(),
                yielded.agent(), taskId, agent, true,
                "agent resource reservation yielded to human floor on " + item);
            conflicts.add(conflict);
            conflictLog.add(conflict);
        }
        return conflicts;
    }
}
