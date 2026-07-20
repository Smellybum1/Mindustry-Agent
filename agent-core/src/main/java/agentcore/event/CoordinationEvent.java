package agentcore.event;

import agentcore.AgentId;
import agentcore.CoordinationAct;
import agentcore.TaskType;
import agentcore.task.ResourceCost;
import agentcore.task.TaskStatus;

import java.util.List;
import java.util.Objects;
import java.util.Set;

/**
 * An immutable record of one board state transition (brief §11.3 message schema,
 * §21.2 event log). Every mutation of the {@code TaskBoard} emits exactly one of
 * these into the {@link EventLog}; telemetry and the protocol layer serialize
 * them, and {@code AnnouncementRenderer} renders the human-facing subset.
 *
 * <p>The {@link #act()} is the coordination act when an agent originated the
 * transition; it is {@code null} for board-internal lifecycle transitions that
 * have no act in the vocabulary — task <em>proposal</em> and lease
 * <em>expiry</em>. For those, {@link #fromStatus()}/{@link #toStatus()} still
 * describe the transition. Keeping the act nullable lets the board honour "every
 * state transition emits an event" without inventing acts outside brief §11.2.
 *
 * <p>{@link #announce()} is set by the {@link RateLimiter} and indicates whether
 * this event should also be rendered as a human-facing announcement (brief
 * §11.7). The structured event is always logged regardless.
 *
 * <p>Built via {@link #builder()}; unpopulated fields carry documented neutral
 * defaults, matching brief §11.3 ("Not every field is populated for every act").
 */
public final class CoordinationEvent{
    private final long messageId;
    private final long episodeId;
    private final long tick;
    private final AgentId agent;                 // nullable (board-internal)
    private final CoordinationAct act;           // nullable (propose/expire)
    private final String taskId;
    private final TaskType taskType;             // nullable
    private final String targetDescription;      // nullable
    private final double priority;
    private final long estimatedTicks;
    private final ResourceCost estimatedCost;
    private final Set<String> requiredCapabilities;
    private final int helpersRequested;
    private final String offeredContribution;    // nullable
    private final double confidence;
    private final long leaseExpiryTick;
    private final String parentTaskId;           // nullable
    private final List<String> dependencyTaskIds;
    private final String reasonCode;             // nullable
    private final double progress;
    private final TaskStatus fromStatus;         // nullable
    private final TaskStatus toStatus;           // nullable
    private final AgentId relatedAgent;          // nullable (e.g. lead agent for a help act)
    private final boolean announce;

    private CoordinationEvent(Builder b){
        this.messageId = b.messageId;
        this.episodeId = b.episodeId;
        this.tick = b.tick;
        this.agent = b.agent;
        this.act = b.act;
        this.taskId = Objects.requireNonNull(b.taskId, "taskId");
        this.taskType = b.taskType;
        this.targetDescription = b.targetDescription;
        this.priority = b.priority;
        this.estimatedTicks = b.estimatedTicks;
        this.estimatedCost = b.estimatedCost == null ? ResourceCost.empty() : b.estimatedCost;
        this.requiredCapabilities = b.requiredCapabilities == null ? Set.of() : Set.copyOf(b.requiredCapabilities);
        this.helpersRequested = b.helpersRequested;
        this.offeredContribution = b.offeredContribution;
        this.confidence = b.confidence;
        this.leaseExpiryTick = b.leaseExpiryTick;
        this.parentTaskId = b.parentTaskId;
        this.dependencyTaskIds = b.dependencyTaskIds == null ? List.of() : List.copyOf(b.dependencyTaskIds);
        this.reasonCode = b.reasonCode;
        this.progress = b.progress;
        this.fromStatus = b.fromStatus;
        this.toStatus = b.toStatus;
        this.relatedAgent = b.relatedAgent;
        this.announce = b.announce;
    }

    public long messageId(){ return messageId; }
    public long episodeId(){ return episodeId; }
    public long tick(){ return tick; }
    public AgentId agent(){ return agent; }
    public CoordinationAct act(){ return act; }
    public String taskId(){ return taskId; }
    public TaskType taskType(){ return taskType; }
    public String targetDescription(){ return targetDescription; }
    public double priority(){ return priority; }
    public long estimatedTicks(){ return estimatedTicks; }
    public ResourceCost estimatedCost(){ return estimatedCost; }
    public Set<String> requiredCapabilities(){ return requiredCapabilities; }
    public int helpersRequested(){ return helpersRequested; }
    public String offeredContribution(){ return offeredContribution; }
    public double confidence(){ return confidence; }
    public long leaseExpiryTick(){ return leaseExpiryTick; }
    public String parentTaskId(){ return parentTaskId; }
    public List<String> dependencyTaskIds(){ return dependencyTaskIds; }
    public String reasonCode(){ return reasonCode; }
    public double progress(){ return progress; }
    public TaskStatus fromStatus(){ return fromStatus; }
    public TaskStatus toStatus(){ return toStatus; }
    public AgentId relatedAgent(){ return relatedAgent; }
    /** Whether this event should be rendered as a human-facing announcement. */
    public boolean announce(){ return announce; }

    public static Builder builder(){ return new Builder(); }

    @Override public String toString(){
        return "CoordinationEvent[#" + messageId + " t=" + tick
            + " " + (act == null ? "(" + fromStatus + "->" + toStatus + ")" : act)
            + " task=" + taskId + (agent == null ? "" : " agent=" + agent.displayName()) + "]";
    }

    /** Mutable builder; the board fills the schema fields from the {@code TaskSpec}. */
    public static final class Builder{
        private long messageId;
        private long episodeId;
        private long tick;
        private AgentId agent;
        private CoordinationAct act;
        private String taskId;
        private TaskType taskType;
        private String targetDescription;
        private double priority;
        private long estimatedTicks;
        private ResourceCost estimatedCost;
        private Set<String> requiredCapabilities;
        private int helpersRequested;
        private String offeredContribution;
        private double confidence;
        private long leaseExpiryTick = -1;
        private String parentTaskId;
        private List<String> dependencyTaskIds;
        private String reasonCode;
        private double progress;
        private TaskStatus fromStatus;
        private TaskStatus toStatus;
        private AgentId relatedAgent;
        private boolean announce;

        public Builder messageId(long v){ this.messageId = v; return this; }
        public Builder episodeId(long v){ this.episodeId = v; return this; }
        public Builder tick(long v){ this.tick = v; return this; }
        public Builder agent(AgentId v){ this.agent = v; return this; }
        public Builder act(CoordinationAct v){ this.act = v; return this; }
        public Builder taskId(String v){ this.taskId = v; return this; }
        public Builder taskType(TaskType v){ this.taskType = v; return this; }
        public Builder targetDescription(String v){ this.targetDescription = v; return this; }
        public Builder priority(double v){ this.priority = v; return this; }
        public Builder estimatedTicks(long v){ this.estimatedTicks = v; return this; }
        public Builder estimatedCost(ResourceCost v){ this.estimatedCost = v; return this; }
        public Builder requiredCapabilities(Set<String> v){ this.requiredCapabilities = v; return this; }
        public Builder helpersRequested(int v){ this.helpersRequested = v; return this; }
        public Builder offeredContribution(String v){ this.offeredContribution = v; return this; }
        public Builder confidence(double v){ this.confidence = v; return this; }
        public Builder leaseExpiryTick(long v){ this.leaseExpiryTick = v; return this; }
        public Builder parentTaskId(String v){ this.parentTaskId = v; return this; }
        public Builder dependencyTaskIds(List<String> v){ this.dependencyTaskIds = v; return this; }
        public Builder reasonCode(String v){ this.reasonCode = v; return this; }
        public Builder progress(double v){ this.progress = v; return this; }
        public Builder fromStatus(TaskStatus v){ this.fromStatus = v; return this; }
        public Builder toStatus(TaskStatus v){ this.toStatus = v; return this; }
        public Builder relatedAgent(AgentId v){ this.relatedAgent = v; return this; }
        public Builder announce(boolean v){ this.announce = v; return this; }

        public CoordinationEvent build(){ return new CoordinationEvent(this); }
    }
}
