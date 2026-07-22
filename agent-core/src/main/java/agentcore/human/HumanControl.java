package agentcore.human;

import agentcore.*;

import java.util.*;

/** Engine-free structured human command parser and simulation-thread control state. */
public final class HumanControl{
    public static final int MAX_ACTIVE_GOALS = 4;

    public enum CommandType{ GOAL, CANCEL, ASSIGN, RELEASE, AUTONOMY, QUIET }
    public enum GoalStatus{ ACTIVE, CANCELLED }
    public enum AutonomyLevel{ LOW, NORMAL, HIGH }

    public record Command(CommandType type, TaskType taskType, String regionId,
                          String goalId, int agentIndex, AutonomyLevel autonomy,
                          Boolean quiet, String authorId){
        public Command{
            Objects.requireNonNull(type, "type");
            authorId = canonicalIdentity(authorId, "author");
            regionId = regionId == null || regionId.isEmpty()
                ? "" : canonicalIdentity(regionId, "region");
            goalId = goalId == null || goalId.isEmpty()
                ? "" : canonicalGoalId(goalId);
            switch(type){
                case GOAL -> {
                    Objects.requireNonNull(taskType, "taskType");
                    if(regionId.isEmpty()) throw new IllegalArgumentException("region required");
                }
                case CANCEL -> requireGoal(goalId);
                case ASSIGN -> {
                    requireGoal(goalId);
                    requireAgent(agentIndex);
                }
                case RELEASE -> requireAgent(agentIndex);
                case AUTONOMY -> Objects.requireNonNull(autonomy, "autonomy");
                case QUIET -> Objects.requireNonNull(quiet, "quiet");
            }
        }
    }

    public record ParseResult(Command command, String reason){
        public boolean accepted(){ return command != null; }
        public static ParseResult accepted(Command command){
            return new ParseResult(Objects.requireNonNull(command), "queued");
        }
        public static ParseResult rejected(String reason){
            return new ParseResult(null, Objects.requireNonNull(reason));
        }
    }

    public record Goal(String id, TaskType taskType, String regionId, String authorId,
                       long creationTick, long revision, GoalStatus status){}
    public record Assignment(int agentIndex, String goalId){}
    public record Snapshot(List<Goal> activeGoals, List<Assignment> assignments,
                           AutonomyLevel autonomy, boolean quiet, long revision){
        public Snapshot{
            activeGoals = List.copyOf(activeGoals);
            assignments = List.copyOf(assignments);
            Objects.requireNonNull(autonomy, "autonomy");
        }
    }
    public record Event(long tick, Command command, boolean accepted, String reason,
                        long revision, String goalId, int agentIndex){}
    public record EnqueueResult(ParseResult parsed, long sequence){
        public boolean accepted(){ return parsed.accepted(); }
    }
    public record AppliedCommand(long sequence, Event event){}
    public record Context(Set<String> regionIds, int agentCount){
        public Context{
            TreeSet<String> canonical = new TreeSet<>();
            for(String region : regionIds == null ? Set.<String>of() : regionIds){
                canonical.add(canonicalIdentity(region, "region"));
            }
            regionIds = Set.copyOf(canonical);
            if(agentCount < 0) throw new IllegalArgumentException("agentCount must be non-negative");
        }
    }

    /** Thread-safe parser queue; only {@link #drain} may touch mutable control state. */
    public static final class CommandQueue{
        private final ArrayDeque<QueuedCommand> pending = new ArrayDeque<>();
        private long nextSequence;

        public EnqueueResult enqueue(String[] tokens, String authorId){
            ParseResult parsed = parse(tokens, authorId);
            if(!parsed.accepted()) return new EnqueueResult(parsed, 0L);
            synchronized(pending){
                long sequence = ++nextSequence;
                pending.addLast(new QueuedCommand(sequence, parsed.command()));
                return new EnqueueResult(parsed, sequence);
            }
        }

        public List<AppliedCommand> drain(State state, long tick, Context context){
            Objects.requireNonNull(state, "state");
            Objects.requireNonNull(context, "context");
            ArrayList<QueuedCommand> commands = new ArrayList<>();
            synchronized(pending){
                while(!pending.isEmpty()) commands.add(pending.removeFirst());
            }
            ArrayList<AppliedCommand> results = new ArrayList<>(commands.size());
            for(QueuedCommand queued : commands){
                results.add(new AppliedCommand(queued.sequence(),
                    state.apply(queued.command(), tick, context)));
            }
            return List.copyOf(results);
        }

        public int pending(){
            synchronized(pending){
                return pending.size();
            }
        }

        public void clear(){
            synchronized(pending){
                pending.clear();
            }
        }
    }

    public static String renderQueued(EnqueueResult result){
        Objects.requireNonNull(result, "result");
        if(!result.accepted()) return "agents: command rejected reason=" + result.parsed().reason();
        return "agents: command queued sequence=" + result.sequence() + " type="
            + result.parsed().command().type().name().toLowerCase(Locale.ROOT);
    }

    public static String render(Event event){
        Objects.requireNonNull(event, "event");
        StringBuilder line = new StringBuilder("agents: command ")
            .append(event.accepted() ? "applied" : "rejected")
            .append(" type=")
            .append(event.command().type().name().toLowerCase(Locale.ROOT))
            .append(" reason=").append(event.reason())
            .append(" revision=").append(event.revision());
        if(!event.goalId().isEmpty()) line.append(" goal=").append(event.goalId());
        if(event.agentIndex() >= 0) line.append(" agent=").append(event.agentIndex());
        return line.toString();
    }

    public static boolean shouldRenderCoordination(boolean quiet, String act){
        return !quiet || "BLOCKED".equals(act);
    }

    /** Stateless token parser; no scenario, board, registry, or world reads occur here. */
    public static ParseResult parse(String[] tokens, String authorId){
        if(tokens == null || tokens.length == 0) return ParseResult.rejected("missing_command");
        String keyword = tokens[0].toLowerCase(Locale.ROOT);
        try{
            return switch(keyword){
                case "goal" -> tokens.length == 3
                    ? ParseResult.accepted(new Command(CommandType.GOAL,
                        taskType(tokens[1]), canonicalIdentity(tokens[2], "region"),
                        "", -1, null, null, authorId))
                    : ParseResult.rejected("usage_goal");
                case "cancel" -> tokens.length == 2
                    ? ParseResult.accepted(new Command(CommandType.CANCEL, null, "",
                        canonicalGoalId(tokens[1]), -1, null, null, authorId))
                    : ParseResult.rejected("usage_cancel");
                case "assign" -> tokens.length == 3
                    ? ParseResult.accepted(new Command(CommandType.ASSIGN, null, "",
                        canonicalGoalId(tokens[2]), agentIndex(tokens[1]), null, null, authorId))
                    : ParseResult.rejected("usage_assign");
                case "release" -> tokens.length == 2
                    ? ParseResult.accepted(new Command(CommandType.RELEASE, null, "", "",
                        agentIndex(tokens[1]), null, null, authorId))
                    : ParseResult.rejected("usage_release");
                case "autonomy" -> tokens.length == 2
                    ? ParseResult.accepted(new Command(CommandType.AUTONOMY, null, "", "", -1,
                        AutonomyLevel.valueOf(tokens[1].toUpperCase(Locale.ROOT)), null, authorId))
                    : ParseResult.rejected("usage_autonomy");
                case "quiet" -> tokens.length == 2
                    ? ParseResult.accepted(new Command(CommandType.QUIET, null, "", "", -1,
                        null, onOff(tokens[1]), authorId))
                    : ParseResult.rejected("usage_quiet");
                default -> ParseResult.rejected("unknown_command");
            };
        }catch(IllegalArgumentException e){
            return ParseResult.rejected("invalid_argument");
        }
    }

    /** Mutable state owned by exactly one simulation thread. */
    public static final class State{
        private final LinkedHashMap<String, Goal> goals = new LinkedHashMap<>();
        private final TreeMap<Integer, String> assignments = new TreeMap<>();
        private AutonomyLevel autonomy = AutonomyLevel.NORMAL;
        private boolean quiet;
        private long revision;
        private long goalSequence;

        public void reset(){
            goals.clear();
            assignments.clear();
            autonomy = AutonomyLevel.NORMAL;
            quiet = false;
            revision = 0L;
            goalSequence = 0L;
        }

        public Snapshot snapshot(){
            ArrayList<Goal> active = new ArrayList<>();
            for(Goal goal : goals.values()) if(goal.status() == GoalStatus.ACTIVE) active.add(goal);
            ArrayList<Assignment> bound = new ArrayList<>();
            assignments.forEach((agent, goal) -> bound.add(new Assignment(agent, goal)));
            return new Snapshot(active, bound, autonomy, quiet, revision);
        }

        public Event apply(Command command, long tick, Context context){
            Objects.requireNonNull(command, "command");
            Objects.requireNonNull(context, "context");
            return switch(command.type()){
                case GOAL -> addGoal(command, tick, context);
                case CANCEL -> cancel(command, tick);
                case ASSIGN -> assign(command, tick, context);
                case RELEASE -> release(command, tick, context);
                case AUTONOMY -> autonomy(command, tick);
                case QUIET -> quiet(command, tick);
            };
        }

        private Event addGoal(Command command, long tick, Context context){
            if(!context.regionIds().contains(command.regionId())){
                return rejected(command, tick, "unknown_region", "", -1);
            }
            for(Goal goal : goals.values()){
                if(goal.status() == GoalStatus.ACTIVE && goal.taskType() == command.taskType()
                    && goal.regionId().equals(command.regionId())){
                    return rejected(command, tick, "duplicate_goal", goal.id(), -1);
                }
            }
            int activeCount = 0;
            for(Goal goal : goals.values()){
                if(goal.status() == GoalStatus.ACTIVE) activeCount++;
            }
            if(activeCount >= MAX_ACTIVE_GOALS){
                return rejected(command, tick, "goal_limit", "", -1);
            }
            long nextRevision = revision + 1L;
            String id = "human:goal:" + (++goalSequence);
            goals.put(id, new Goal(id, command.taskType(), command.regionId(), command.authorId(),
                tick, nextRevision, GoalStatus.ACTIVE));
            revision = nextRevision;
            return accepted(command, tick, id, -1);
        }

        private Event cancel(Command command, long tick){
            Goal goal = activeGoal(command.goalId());
            if(goal == null) return rejected(command, tick, "unknown_goal", command.goalId(), -1);
            revision++;
            goals.put(goal.id(), new Goal(goal.id(), goal.taskType(), goal.regionId(),
                goal.authorId(), goal.creationTick(), revision, GoalStatus.CANCELLED));
            assignments.values().removeIf(goal.id()::equals);
            return accepted(command, tick, goal.id(), -1);
        }

        private Event assign(Command command, long tick, Context context){
            if(command.agentIndex() < 0 || command.agentIndex() >= context.agentCount()){
                return rejected(command, tick, "unknown_agent", command.goalId(), command.agentIndex());
            }
            Goal goal = activeGoal(command.goalId());
            if(goal == null){
                return rejected(command, tick, "unknown_goal", command.goalId(), command.agentIndex());
            }
            if(assignments.containsKey(command.agentIndex())){
                return rejected(command, tick, "agent_already_assigned", goal.id(), command.agentIndex());
            }
            if(assignments.containsValue(goal.id())){
                return rejected(command, tick, "goal_already_assigned", goal.id(), command.agentIndex());
            }
            assignments.put(command.agentIndex(), goal.id());
            revision++;
            return accepted(command, tick, goal.id(), command.agentIndex());
        }

        private Event release(Command command, long tick, Context context){
            if(command.agentIndex() < 0 || command.agentIndex() >= context.agentCount()){
                return rejected(command, tick, "unknown_agent", "", command.agentIndex());
            }
            String goal = assignments.remove(command.agentIndex());
            if(goal == null) return rejected(command, tick, "agent_not_assigned", "", command.agentIndex());
            revision++;
            return accepted(command, tick, goal, command.agentIndex());
        }

        private Event autonomy(Command command, long tick){
            if(autonomy == command.autonomy()) return rejected(command, tick, "no_change", "", -1);
            autonomy = command.autonomy();
            revision++;
            return accepted(command, tick, "", -1);
        }

        private Event quiet(Command command, long tick){
            if(quiet == command.quiet()) return rejected(command, tick, "no_change", "", -1);
            quiet = command.quiet();
            revision++;
            return accepted(command, tick, "", -1);
        }

        private Goal activeGoal(String id){
            Goal goal = goals.get(id);
            return goal != null && goal.status() == GoalStatus.ACTIVE ? goal : null;
        }

        private Event accepted(Command command, long tick, String goalId, int agent){
            return new Event(tick, command, true, "applied", revision, goalId, agent);
        }

        private Event rejected(Command command, long tick, String reason, String goalId, int agent){
            return new Event(tick, command, false, reason, revision, goalId, agent);
        }
    }

    private static TaskType taskType(String value){
        return TaskType.valueOf(value.toUpperCase(Locale.ROOT).replace('-', '_'));
    }

    private static int agentIndex(String value){
        int parsed = Integer.parseInt(value);
        if(parsed < 0) throw new IllegalArgumentException("negative agent");
        return parsed;
    }

    private static Boolean onOff(String value){
        if(value.equalsIgnoreCase("on")) return true;
        if(value.equalsIgnoreCase("off")) return false;
        throw new IllegalArgumentException("expected on or off");
    }

    private static String canonicalGoalId(String value){
        String canonical = value.toLowerCase(Locale.ROOT);
        if(!canonical.matches("human:goal:[1-9][0-9]*")){
            throw new IllegalArgumentException("invalid goal id");
        }
        return canonical;
    }

    private static String canonicalIdentity(String value, String label){
        String canonical = value == null ? "" : value.trim().toLowerCase(Locale.ROOT);
        if(!canonical.matches("[a-z0-9][a-z0-9_.:-]{0,63}")){
            throw new IllegalArgumentException("invalid " + label);
        }
        return canonical;
    }

    private static void requireGoal(String goalId){
        if(goalId.isEmpty()) throw new IllegalArgumentException("goal required");
    }

    private static void requireAgent(int agentIndex){
        if(agentIndex < 0) throw new IllegalArgumentException("agent required");
    }

    private record QueuedCommand(long sequence, Command command){}

    private HumanControl(){}
}
