package agentcore.task;

import agentcore.TaskType;

import java.util.Collections;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Objects;
import java.util.Set;
import java.util.TreeSet;

/**
 * The immutable definition of a claimable task (brief §10.1, §11.3).
 *
 * <p>A {@code TaskSpec} is the static description that goes onto the board; the
 * mutable, per-episode lifecycle (owner, helpers, lease, progress) lives in
 * {@link TaskState}. Fields mirror the announcement schema of brief §11.3 so a
 * spec can be serialized into a coordination message with no translation.
 *
 * <p>Instances are created through {@link #builder(String, TaskType)}; all
 * collections are defensively copied and exposed unmodifiable, and
 * {@link #requiredCapabilities} is kept in a stable sorted order for
 * determinism.
 */
public final class TaskSpec{
    private final String taskId;
    private final TaskType type;
    private final Target target;
    private final double priority;
    private final long estimatedTicks;
    private final ResourceCost estimatedCost;
    private final Set<String> requiredCapabilities;
    private final int helpersRequested;
    private final boolean exclusive;
    private final String parentTaskId;      // nullable
    private final List<String> dependencyTaskIds;

    private TaskSpec(Builder b){
        this.taskId = Objects.requireNonNull(b.taskId, "taskId");
        this.type = Objects.requireNonNull(b.type, "type");
        this.target = b.target;
        this.priority = b.priority;
        this.estimatedTicks = b.estimatedTicks;
        this.estimatedCost = b.estimatedCost == null ? ResourceCost.empty() : b.estimatedCost;
        // Sorted, unmodifiable copy for deterministic iteration.
        this.requiredCapabilities = Collections.unmodifiableSet(new LinkedHashSet<>(new TreeSet<>(b.requiredCapabilities)));
        this.helpersRequested = b.helpersRequested;
        this.exclusive = b.exclusive;
        this.parentTaskId = b.parentTaskId;
        this.dependencyTaskIds = List.copyOf(b.dependencyTaskIds);
        if(helpersRequested < 0) throw new IllegalArgumentException("helpersRequested must be >= 0");
        if(estimatedTicks < 0) throw new IllegalArgumentException("estimatedTicks must be >= 0");
    }

    public String taskId(){ return taskId; }
    public TaskType type(){ return type; }
    /** The thing acted upon; may be null for target-less tasks like {@code WAIT}. */
    public Target target(){ return target; }
    /** Scenario/utility priority in [0,1] by convention (not enforced). */
    public double priority(){ return priority; }
    public long estimatedTicks(){ return estimatedTicks; }
    public ResourceCost estimatedCost(){ return estimatedCost; }
    /** Capabilities an agent must have to own this task, ascending order. */
    public Set<String> requiredCapabilities(){ return requiredCapabilities; }
    /** How many helpers the owner would like; 0 means solo. */
    public int helpersRequested(){ return helpersRequested; }
    /**
     * Whether at most one agent may own this task at a time. Exclusive tasks back
     * the safety property "no two agents validly own the same exclusive task"
     * (brief §23.5). Non-exclusive tasks (e.g. a shared defence) may be co-owned;
     * helpers are always additive and orthogonal to exclusivity.
     */
    public boolean exclusive(){ return exclusive; }
    /** Parent task in a decomposition, or null. */
    public String parentTaskId(){ return parentTaskId; }
    /** Tasks that must complete first (brief §11.3 {@code dependency_task_ids}). */
    public List<String> dependencyTaskIds(){ return dependencyTaskIds; }

    public static Builder builder(String taskId, TaskType type){
        return new Builder(taskId, type);
    }

    @Override public boolean equals(Object o){
        if(this == o) return true;
        if(!(o instanceof TaskSpec other)) return false;
        return taskId.equals(other.taskId);
    }

    @Override public int hashCode(){
        return taskId.hashCode();
    }

    @Override public String toString(){
        return "TaskSpec[" + taskId + " " + type + (target == null ? "" : " @ " + target.describe()) + "]";
    }

    /** Fluent, defaulting builder for {@link TaskSpec}. */
    public static final class Builder{
        private final String taskId;
        private final TaskType type;
        private Target target;
        private double priority;
        private long estimatedTicks;
        private ResourceCost estimatedCost = ResourceCost.empty();
        private Set<String> requiredCapabilities = Set.of();
        private int helpersRequested;
        private boolean exclusive = true;
        private String parentTaskId;
        private List<String> dependencyTaskIds = List.of();

        private Builder(String taskId, TaskType type){
            this.taskId = taskId;
            this.type = type;
        }

        public Builder target(Target target){ this.target = target; return this; }
        public Builder priority(double priority){ this.priority = priority; return this; }
        public Builder estimatedTicks(long ticks){ this.estimatedTicks = ticks; return this; }
        public Builder estimatedCost(ResourceCost cost){ this.estimatedCost = cost; return this; }
        public Builder requiredCapabilities(Set<String> caps){ this.requiredCapabilities = Objects.requireNonNull(caps); return this; }
        public Builder helpersRequested(int n){ this.helpersRequested = n; return this; }
        public Builder exclusive(boolean exclusive){ this.exclusive = exclusive; return this; }
        public Builder parentTaskId(String parentTaskId){ this.parentTaskId = parentTaskId; return this; }
        public Builder dependencyTaskIds(List<String> deps){ this.dependencyTaskIds = Objects.requireNonNull(deps); return this; }

        public TaskSpec build(){ return new TaskSpec(this); }
    }
}
