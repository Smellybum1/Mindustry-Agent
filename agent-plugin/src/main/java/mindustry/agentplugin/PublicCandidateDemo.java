package mindustry.agentplugin;

import agentcore.candidates.*;
import agentcore.policy.*;
import agentcore.policy.GreedyUtilityPolicy.*;
import agentcore.skill.*;
import arc.util.serialization.*;
import mindustry.gen.*;
import mindustry.rl.*;

import java.nio.charset.*;
import java.security.*;
import java.util.*;

import static mindustry.Vars.*;

/** Simulation-thread public-candidate policy runtime for the real-time demo. */
final class PublicCandidateDemo{
    private static final long decisionInterval = 30L;

    private final DemoAgentRegistry registry;
    private final AdaptiveWorldFacts facts;
    private final EngineCandidates candidates;
    private final CoordinationAdapter coordination;
    private final GreedyUtilityPolicy policy = new GreedyUtilityPolicy();
    private final ArrayList<String> acceptedSelections = new ArrayList<>();
    private CandidateSet[] boundaryCandidates = new CandidateSet[0];
    private long nextDecisionTick;
    private long decisionRevision;
    private int previousEnemies;
    private int previousCoreHealth;
    private boolean started;

    PublicCandidateDemo(Scenario scenario, DemoAgentRegistry registry){
        this.registry = registry;
        facts = new AdaptiveWorldFacts(scenario, registry);
        candidates = new EngineCandidates(scenario, registry, facts);
        coordination = new CoordinationAdapter(scenario, registry, facts);
        candidates.setCoordination(coordination);
    }

    void start(){
        if(started) return;
        started = true;
        coordination.reset(1L, registry.size());
        facts.reset();
        policy.reset();
        acceptedSelections.clear();
        nextDecisionTick = (long)state.tick;
        decisionRevision = coordination.decisionRevision();
        previousEnemies = enemyCount();
        previousCoreHealth = coreHealth();
        decide((long)state.tick);
    }

    void update(){
        long tick = (long)state.tick;
        facts.recordTick(0);
        coordination.recordMetricsTick();
        coordination.tick(tick);

        int enemies = enemyCount();
        int health = coreHealth();
        boolean worldBoundary = (previousEnemies == 0) != (enemies == 0)
            || health < previousCoreHealth;
        if(tick >= nextDecisionTick || coordination.decisionRevision() != decisionRevision
            || worldBoundary){
            decide(tick);
        }
        previousEnemies = enemies;
        previousCoreHealth = health;
    }

    void stop(String reason){
        Jval actions = Jval.newArray();
        for(int i = 0; i < registry.size(); i++){
            Jval action = Jval.newObject();
            action.put("agent_id", i);
            Jval task = Jval.newObject();
            task.put("type", "ABANDON");
            task.put("reason", reason);
            action.add("task_action", task);
            actions.add(action);
        }
        coordination.applyActions(actions, boundaryCandidates);
    }

    Jval drainEvents(){ return coordination.drainEvents(); }
    Jval metrics(){ return coordination.metrics(); }
    boolean started(){ return started; }
    int taskCount(){ return coordination.board().tasks().size(); }
    boolean preparationComplete(){
        CandidateWorldSnapshot world = candidates.snapshot();
        return facts.economy().operational() && world.buildLineComplete()
            && world.schematicComplete() && world.plannedSchematics().isEmpty()
            && facts.defense().readiness() >= 1.0;
    }
    String phase(){
        if(enemyCount() > 0) return "defend";
        return preparationComplete() ? "reserve-mining" : "opening";
    }
    int selectionCount(){ return acceptedSelections.size(); }

    String selectionDigest(){
        try{
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            for(String row : acceptedSelections){
                digest.update(row.getBytes(StandardCharsets.UTF_8));
                digest.update((byte)'\n');
            }
            return HexFormat.of().formatHex(digest.digest());
        }catch(NoSuchAlgorithmException e){
            throw new IllegalStateException("SHA-256 unavailable", e);
        }
    }

    private void decide(long tick){
        for(int i = 0; i < registry.size(); i++){
            if(!registry.available(i)) registry.ensureAgent(i);
        }

        CandidateWorldSnapshot world = candidates.snapshot();
        boundaryCandidates = new CandidateSet[registry.size()];
        ArrayList<AgentView> views = new ArrayList<>();
        Jval[] masks = new Jval[registry.size()];
        for(DemoAgentRegistry.Agent agent : registry.agents()){
            CandidateSet set = candidates.generate(agent, world);
            boundaryCandidates[agent.index()] = set;
            Jval rawMask = coordination.actionMask(agent.index(), set);
            masks[agent.index()] = rawMask;
            SkillResult result = agent.controller().lastResult();
            views.add(new AgentView(agent.index(), agent.controller().activeType(),
                result.status(), result.reason(), set, mask(rawMask)));
        }

        List<Action> selected = policy.actions(views,
            new TeamView(tick, world.enemyCount(), world.defenseReadiness().ammoCoverage()));
        Jval payload = Jval.newArray();
        for(Action action : selected) payload.add(action(action));
        Jval results = coordination.applyActions(payload, boundaryCandidates);

        ArrayList<ActionResult> accepted = new ArrayList<>();
        for(int i = 0; i < selected.size(); i++){
            Action action = selected.get(i);
            Jval result = results.asArray().get(i);
            boolean ok = result.getBool("accepted", false);
            accepted.add(new ActionResult(action.agentIndex(), ok));
            if(ok && action.type() == ActionType.SELECT_CANDIDATE_TASK){
                TaskCandidate candidate = boundaryCandidates[action.agentIndex()]
                    .candidates().get(action.candidateIndex());
                acceptedSelections.add(action.agentIndex() + "\u001f"
                    + normalizeTaskId(candidate.task().taskId()) + "\u001f"
                    + candidate.task().type().name());
            }
        }
        policy.observeActionResults(accepted);
        decisionRevision = coordination.decisionRevision();
        nextDecisionTick = tick + decisionInterval;
    }

    private static ActionMask mask(Jval raw){
        ArrayList<Boolean> candidateMask = new ArrayList<>();
        Jval values = raw.get("candidate_task");
        if(values != null && values.isArray()){
            for(Jval value : values.asArray()) candidateMask.add(value.asBool());
        }
        return new ActionMask(candidateMask,
            raw.getBool("continue_current_task", false), raw.getBool("abandon", false));
    }

    private static Jval action(Action selected){
        Jval out = Jval.newObject();
        out.put("agent_id", selected.agentIndex());
        Jval task = Jval.newObject();
        task.put("type", selected.type().name());
        if(selected.type() == ActionType.SELECT_CANDIDATE_TASK){
            task.put("candidate_index", selected.candidateIndex());
        }else if(selected.type() == ActionType.ABANDON){
            task.put("reason", selected.reason());
        }
        out.add("task_action", task);
        return out;
    }

    private static String normalizeTaskId(String taskId){
        return taskId.replaceFirst(":at-[0-9]+$", ":at-*");
    }

    private static int enemyCount(){
        int count = 0;
        for(Unit unit : Groups.unit) if(unit.team == state.rules.waveTeam && !unit.dead()) count++;
        return count;
    }

    private static int coreHealth(){
        Building core = state.rules.defaultTeam.core();
        return core == null ? 0 : Math.round(core.health);
    }
}
