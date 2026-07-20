package mindustry.rl;

import agentcore.board.*;
import agentcore.reservation.*;
import agentcore.task.*;
import arc.struct.*;
import mindustry.entities.units.*;
import mindustry.game.*;
import mindustry.game.Teams.*;
import mindustry.gen.*;
import mindustry.type.*;
import mindustry.world.blocks.defense.turrets.Turret.*;
import mindustry.world.blocks.storage.CoreBlock.*;

import java.io.*;
import java.security.*;
import java.util.*;

import static mindustry.Vars.*;

/**
 * Canonical, history-independent state hash (docs/ENGINE_NOTES.md §10).
 *
 * <p>Algorithm: SHA-256 over a deterministically ordered byte stream. Entities are
 * <b>sorted by id</b> before hashing because {@code EntityGroup} iteration order is
 * swap-remove / history dependent. Floating-point quantities (positions, health) are
 * quantized by rounding {@code value * 1000} to a {@code long} — i.e. precision
 * <b>1e-3</b> — before hashing, so bit-level FP jitter cannot change the hash while
 * meaningful state differences still do. Absolute entity ids are hashed only after
 * {@code EntityGroup.lastId} is reset per episode (see {@link RlServer}), so identical
 * scenarios across episodes/JVMs produce identical hashes.
 *
 * <p>Inputs: {@code state.tick}, {@code state.wave}, per-core team + item counts, all
 * buildings (sorted by id: block/team/quantized pos/health/turret ammo), all units
 * (sorted by id: type/team/quantized pose/health/cargo/ordered build plans), and
 * active-team broken-block queues in team-id then queue order, and non-empty M5
 * task-board lifecycle/helper state in insertion order. Never includes
 * {@code Fx}/render/{@code Time.millis} or the drained event transport buffer.
 */
public final class StateHasher{
    private static final long QUANT = 1000L; //1e-3 precision

    private StateHasher(){}

    public static String hash(){
        return hash(null, null);
    }

    public static String hash(RlAgentRegistry registry){
        return hash(registry, null);
    }

    public static String hash(RlAgentRegistry registry, TaskBoard board){
        try{
            MessageDigest md = MessageDigest.getInstance("SHA-256");
            DataOutputStream out = new DataOutputStream(new DigestOutputStream(md));

            //tick is a double advanced by exactly +1.0 per update; hash the exact bits
            out.writeLong(Double.doubleToLongBits(state.tick));
            out.writeInt(state.wave);
            //scenario wave counters: wavetime decrements by the fixed delta (bit-exact), and
            //the live wave-team unit count. Both deterministic; they fingerprint the wave phase.
            out.writeInt(Float.floatToIntBits(state.wavetime));
            out.writeInt(state.enemies);
            out.writeBoolean(state.gameOver);

            //cores, sorted by team id for stability
            Seq<CoreBuild> cores = new Seq<>();
            for(Teams.TeamData td : state.teams.getActive()){
                cores.addAll(td.cores);
            }
            cores.sort(Comparator.comparingInt(c -> c.id()));
            out.writeInt(cores.size);
            for(CoreBuild core : cores){
                out.writeInt(core.team().id);
                writeItems(out, core.items);
            }

            //buildings, sorted by id
            Seq<Building> builds = new Seq<>();
            for(Building b : Groups.build){
                builds.add(b);
            }
            builds.sort(Comparator.comparingInt(b -> b.id()));
            out.writeInt(builds.size);
            for(Building b : builds){
                out.writeInt(b.id());
                out.writeInt(b.block.id);
                out.writeInt(b.team().id);
                out.writeLong(quant(b.x));
                out.writeLong(quant(b.y));
                out.writeLong(quant(b.health));
                if(b instanceof TurretBuild turret){
                    out.writeBoolean(true);
                    out.writeInt(turret.totalAmmo);
                }else{
                    out.writeBoolean(false);
                }
            }

            //units, sorted by id (none in M1, but future-proof and part of the canon)
            Seq<Unit> units = new Seq<>();
            for(Unit u : Groups.unit){
                units.add(u);
            }
            units.sort(Comparator.comparingInt(u -> u.id()));
            out.writeInt(units.size);
            for(Unit u : units){
                out.writeInt(u.id());
                out.writeInt(u.type == null ? -1 : u.type.id);
                out.writeInt(u.team().id);
                out.writeLong(quant(u.x));
                out.writeLong(quant(u.y));
                out.writeLong(quant(u.vel().x));
                out.writeLong(quant(u.vel().y));
                out.writeLong(quant(u.health));
                //cargo: agent units carry mined ore — part of the canonical fingerprint (D7)
                Item carried = u.item();
                if(carried != null){
                    out.writeInt(carried.id);
                    out.writeInt(u.stack().amount);
                }else{
                    out.writeInt(-1);
                    out.writeInt(0);
                }

                //BuilderComp owns an ordered Seq; index order is the execution order.
                out.writeInt(u.plans().size);
                for(BuildPlan plan : u.plans()){
                    out.writeBoolean(plan.breaking);
                    out.writeInt(plan.block == null ? -1 : plan.block.id);
                    out.writeInt(plan.x);
                    out.writeInt(plan.y);
                    out.writeInt(plan.rotation);
                    out.writeLong(quant(plan.progress));
                }
            }

            //Ghost rebuild plans are an ordered Queue per active team. Include removed
            //markers because they affect the next stable snapshot/removal pass.
            Seq<TeamData> teamData = new Seq<>();
            teamData.addAll(state.teams.getActive());
            teamData.sort(Comparator.comparingInt(td -> td.team.id));
            out.writeInt(teamData.size);
            for(TeamData data : teamData){
                out.writeInt(data.team.id);
                out.writeInt(data.plans.size);
                for(int i = 0; i < data.plans.size; i++){
                    BlockPlan plan = data.plans.get(i);
                    out.writeInt(plan.block == null ? -1 : plan.block.id);
                    out.writeInt(plan.x);
                    out.writeInt(plan.y);
                    out.writeInt(plan.rotation);
                    out.writeBoolean(plan.removed);
                }
            }

            //agent registry + active skill state (D7): golden replays break if a skill
            //state machine changes behaviour. Iterated in dense index order (deterministic).
            if(registry != null){
                out.writeInt(registry.size());
                for(RlAgentRegistry.Agent agent : registry.agents()){
                    out.writeInt(agent.index);
                    out.writeInt(agent.unit.id());
                    byte[] typeBytes = agent.controller.activeType()
                        .getBytes(java.nio.charset.StandardCharsets.UTF_8);
                    out.writeInt(typeBytes.length);
                    out.write(typeBytes);
                    var result = agent.controller.lastResult();
                    out.writeInt(result.status().ordinal());
                    out.writeInt(result.reason().ordinal());
                    out.writeLong(quant(result.progress()));
                }
            }else{
                out.writeInt(0);
            }

            //M5 coordination state in board insertion order. The pending event buffer is
            //transport state and excluded, but the next message id affects future telemetry.
            List<TaskState> boardTasks = board == null ? List.of() : board.tasks();
            if(!boardTasks.isEmpty()){
                out.writeInt(0x4d35424f); //"M5BO" section marker; absent preserves pre-M5 empty-board hashes.
                List<TaskState> tasks = boardTasks;
                out.writeInt(tasks.size());
                for(TaskState task : tasks){
                    TaskSpec spec = task.spec();
                    writeString(out, spec.taskId());
                    out.writeInt(spec.type().ordinal());
                    writeString(out, spec.target() == null ? "" : spec.target().describe());
                    out.writeLong(Double.doubleToLongBits(spec.priority()));
                    out.writeLong(spec.estimatedTicks());
                    out.writeInt(spec.estimatedCost().asMap().size());
                    for(Map.Entry<String, Integer> cost : spec.estimatedCost().asMap().entrySet()){
                        writeString(out, cost.getKey());
                        out.writeInt(cost.getValue());
                    }
                    out.writeInt(spec.requiredCapabilities().size());
                    for(String capability : spec.requiredCapabilities()) writeString(out, capability);
                    out.writeInt(spec.helpersRequested());
                    out.writeBoolean(spec.exclusive());
                    writeString(out, spec.parentTaskId() == null ? "" : spec.parentTaskId());
                    out.writeInt(spec.dependencyTaskIds().size());
                    for(String dependency : spec.dependencyTaskIds()) writeString(out, dependency);

                    out.writeInt(task.status().ordinal());
                    out.writeInt(task.owner() == null ? -1 : task.owner().index());
                    out.writeLong(task.leaseExpiryTick());
                    out.writeLong(Math.round(task.progress() * QUANT));
                    writeString(out, task.reasonCode() == null ? "" : task.reasonCode());
                    out.writeInt(task.pendingOffers().size());
                    for(HelperOffer offer : task.pendingOffers()){
                        out.writeInt(offer.helper().index());
                        writeString(out, offer.contribution());
                        out.writeInt(offer.amount());
                        out.writeLong(offer.offeredTick());
                    }
                    out.writeInt(task.helpers().size());
                    for(HelperContract helper : task.helpers()){
                        out.writeInt(helper.helper().index());
                        writeString(out, helper.contribution());
                        out.writeInt(helper.amount());
                        out.writeLong(helper.acceptedTick());
                        out.writeBoolean(helper.fulfilled());
                        out.writeLong(helper.fulfilledTick());
                    }
                }
                List<TileReservation> tileReservations = board.reservations().tileReservations();
                out.writeInt(tileReservations.size());
                for(TileReservation reservation : tileReservations){
                    writeString(out, reservation.taskId());
                    out.writeInt(reservation.agent().index());
                    out.writeInt(reservation.area().x());
                    out.writeInt(reservation.area().y());
                    out.writeInt(reservation.area().w());
                    out.writeInt(reservation.area().h());
                    out.writeBoolean(reservation.human());
                }
                List<ResourceReservation> resourceReservations =
                    board.reservations().resourceReservations();
                out.writeInt(resourceReservations.size());
                for(ResourceReservation reservation : resourceReservations){
                    writeString(out, reservation.taskId());
                    out.writeInt(reservation.agent().index());
                    writeString(out, reservation.item());
                    out.writeInt(reservation.amount());
                    out.writeBoolean(reservation.human());
                }
                List<RegionReservation> regionReservations = board.reservations().regionReservations();
                out.writeInt(regionReservations.size());
                for(RegionReservation reservation : regionReservations){
                    writeString(out, reservation.taskId());
                    out.writeInt(reservation.agent().index());
                    writeString(out, reservation.regionId());
                    out.writeBoolean(reservation.human());
                }
                out.writeLong(board.events().peekNextMessageId());
            }

            out.flush();
            return toHex(md.digest());
        }catch(Exception e){
            throw new RuntimeException("state hash failed", e);
        }
    }

    private static void writeItems(DataOutputStream out, mindustry.world.modules.ItemModule items) throws IOException{
        //hash every item slot in content order for a full inventory fingerprint
        Seq<Item> all = mindustry.Vars.content.items();
        out.writeInt(all.size);
        for(Item item : all){
            out.writeInt(items == null ? 0 : items.get(item));
        }
    }

    private static void writeString(DataOutputStream out, String value) throws IOException{
        byte[] bytes = value.getBytes(java.nio.charset.StandardCharsets.UTF_8);
        out.writeInt(bytes.length);
        out.write(bytes);
    }

    private static long quant(float v){
        return Math.round((double)v * QUANT);
    }

    private static String toHex(byte[] bytes){
        StringBuilder sb = new StringBuilder(bytes.length * 2);
        for(byte b : bytes){
            sb.append(Character.forDigit((b >> 4) & 0xf, 16));
            sb.append(Character.forDigit(b & 0xf, 16));
        }
        return sb.toString();
    }

    /** OutputStream that feeds a MessageDigest (avoids buffering the whole stream). */
    private static final class DigestOutputStream extends OutputStream{
        private final MessageDigest md;
        DigestOutputStream(MessageDigest md){ this.md = md; }
        @Override public void write(int b){ md.update((byte)b); }
        @Override public void write(byte[] b, int off, int len){ md.update(b, off, len); }
    }

    /** Copper/lead helper used by the observation payload. */
    public static int coreItem(Item item){
        CoreBuild core = Team.sharded.core();
        return core == null ? 0 : core.items.get(item);
    }
}
