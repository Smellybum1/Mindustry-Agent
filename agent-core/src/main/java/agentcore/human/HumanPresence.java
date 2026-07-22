package agentcore.human;

import agentcore.reservation.*;

import java.util.*;

/** Deterministic lifecycle for active human plans and recently completed construction. */
public final class HumanPresence{
    public static final long RECENT_CONSTRUCTION_TICKS = 600L;

    public record Plan(String id, Rect area, Map<String, Integer> resources){
        public Plan{
            if(id == null || id.isBlank()) throw new IllegalArgumentException("presence id required");
            Objects.requireNonNull(area, "area");
            TreeMap<String, Integer> canonical = new TreeMap<>();
            for(Map.Entry<String, Integer> entry
                : resources == null ? Map.<String, Integer>of().entrySet() : resources.entrySet()){
                if(entry.getKey() == null || entry.getKey().isBlank()){
                    throw new IllegalArgumentException("resource item required");
                }
                if(entry.getValue() == null || entry.getValue() < 0){
                    throw new IllegalArgumentException("resource amount must be non-negative");
                }
                if(entry.getValue() > 0) canonical.put(entry.getKey(), entry.getValue());
            }
            resources = Collections.unmodifiableMap(canonical);
        }

        public Plan completed(){
            return resources.isEmpty() ? this : new Plan(id, area, Map.of());
        }
    }

    public record Change(List<String> removed, List<Plan> added){
        public Change{
            removed = List.copyOf(removed);
            added = List.copyOf(added);
        }

        public boolean empty(){ return removed.isEmpty() && added.isEmpty(); }
    }

    /** Simulation-thread-owned diff tracker. */
    public static final class Tracker{
        private final TreeMap<String, Plan> applied = new TreeMap<>();
        private final TreeMap<String, Recent> recent = new TreeMap<>();

        public void constructionCompleted(Plan plan, long tick){
            Objects.requireNonNull(plan, "plan");
            recent.put(plan.id(), new Recent(plan.completed(), tick + RECENT_CONSTRUCTION_TICKS));
        }

        public Change update(Collection<Plan> activePlans, long tick){
            recent.entrySet().removeIf(entry -> entry.getValue().expiresTick() <= tick);
            TreeMap<String, Plan> desired = new TreeMap<>();
            for(Recent value : recent.values()) desired.put(value.plan().id(), value.plan());
            for(Plan plan : activePlans == null ? List.<Plan>of() : activePlans){
                desired.put(plan.id(), plan);
            }

            ArrayList<String> removed = new ArrayList<>();
            for(Map.Entry<String, Plan> entry : applied.entrySet()){
                Plan replacement = desired.get(entry.getKey());
                if(replacement == null || !replacement.equals(entry.getValue())){
                    removed.add(entry.getKey());
                }
            }
            ArrayList<Plan> added = new ArrayList<>();
            for(Map.Entry<String, Plan> entry : desired.entrySet()){
                Plan previous = applied.get(entry.getKey());
                if(previous == null || !previous.equals(entry.getValue())) added.add(entry.getValue());
            }
            applied.clear();
            applied.putAll(desired);
            return new Change(removed, added);
        }

        public void reset(){
            applied.clear();
            recent.clear();
        }

        public List<Plan> current(){ return List.copyOf(applied.values()); }
    }

    private record Recent(Plan plan, long expiresTick){}

    private HumanPresence(){}
}
