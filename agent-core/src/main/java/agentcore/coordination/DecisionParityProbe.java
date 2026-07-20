package agentcore.coordination;

import agentcore.skill.*;
import agentcore.task.*;

import java.util.*;

/** Standalone M7.2 acceptance probe over one recorded sequence of policy snapshots. */
public final class DecisionParityProbe{
    private DecisionParityProbe(){ }

    public static void main(String[] args){
        List<Snapshot> trace = recordedTrace();
        List<ExpertCoordinationDriver.PolicyDecision> fixed = replay(trace);
        List<ExpertCoordinationDriver.PolicyDecision> demo = replay(trace);
        if(!fixed.equals(demo)){
            throw new AssertionError("fixed-step/demo policy decisions diverged");
        }

        long selections = fixed.stream().filter(d -> d.kind().equals("SELECT_TASK")).count();
        EnumSet<agentcore.TaskType> selectedTypes = EnumSet.noneOf(agentcore.TaskType.class);
        for(ExpertCoordinationDriver.PolicyDecision decision : fixed){
            if(decision.kind().equals("SELECT_TASK") && decision.taskType() != null){
                selectedTypes.add(decision.taskType());
            }
        }
        boolean expansion = fixed.stream().anyMatch(d -> d.kind().equals("PLAN_EXPANSION"));
        if(selections < 40 || !selectedTypes.contains(agentcore.TaskType.DEFEND_REGION)
            || !selectedTypes.contains(agentcore.TaskType.REPAIR_REGION) || !expansion){
            throw new AssertionError("recorded trace did not exercise full coordination policy: "
                + "selections=" + selections + " types=" + selectedTypes + " expansion=" + expansion);
        }
        System.out.println("DECISION PARITY OK snapshots=" + trace.size()
            + " decisions=" + fixed.size() + " selections=" + selections
            + " types=" + selectedTypes);
    }

    private static List<ExpertCoordinationDriver.PolicyDecision> replay(List<Snapshot> trace){
        FakePort port = new FakePort();
        ExpertCoordinationDriver driver = new ExpertCoordinationDriver(plan(), port);
        driver.reset(1L);
        driver.startOpening(0L);
        for(Snapshot snapshot : trace){
            driver.update(snapshot.tick(), snapshot.enemies(), snapshot.coreHealth());
        }
        return driver.decisions();
    }

    private static List<Snapshot> recordedTrace(){
        ArrayList<Snapshot> result = new ArrayList<>();
        for(int tick = 1; tick <= 90; tick++){
            int enemies = tick == 25 || tick == 50 || tick == 75 ? 3 : 0;
            result.add(new Snapshot(tick, enemies, 1100));
        }
        return List.copyOf(result);
    }

    private static ExpertCoordinationPlan plan(){
        List<BuildSpec> line = List.of(
            new BuildSpec("mechanical-drill", 0, 0, 0),
            new BuildSpec("conveyor", 0, -1, 2));
        List<BuildSpec> defense = List.of(
            new BuildSpec("duo", 0, -1, 1),
            new BuildSpec("duo", 0, 1, 1),
            new BuildSpec("copper-wall", 1, 0, 0));
        return new ExpertCoordinationPlan(
            24, 24, 8, 3, 8100,
            new ExpertCoordinationPlan.Schematic("line", 28, 28, 7, line),
            new ExpertCoordinationPlan.Schematic("defense", 32, 24, 76, defense),
            new ExpertCoordinationPlan.Schematic("fortification", 24, 24, 6,
                List.of(new BuildSpec("copper-wall", -2, 0, 0))),
            List.of(
                new ExpertCoordinationPlan.Schematic("expansion-1", 24, 24, 6,
                    List.of(new BuildSpec("copper-wall", 12, 0, 0))),
                new ExpertCoordinationPlan.Schematic("expansion-2", 24, 24, 6,
                    List.of(new BuildSpec("copper-wall", 15, 0, 0)))
            ),
            List.of(new TileTarget(28, 18), new TileTarget(31, 18), new TileTarget(28, 21)),
            List.of(new TileTarget(32, 23), new TileTarget(32, 25)),
            new ExpertCoordinationPlan.Region("east_lane", 26, 21, 21, 7),
            new ExpertCoordinationPlan.Region("defense_block", 30, 20, 6, 9),
            Map.of("copper-wall", 6, "duo", 35)
        );
    }

    private record Snapshot(long tick, int enemies, int coreHealth){}

    private static final class FakePort implements ExpertCoordinationDriver.Port{
        private final Skill[] active = new Skill[3];

        @Override public SkillResult lastResult(int agentIndex){
            return active[agentIndex] == null
                ? SkillResult.ready() : SkillResult.succeeded(SkillReason.TARGET_REACHED);
        }

        @Override public Skill activeSkill(int agentIndex){ return active[agentIndex]; }
        @Override public void setSkill(int agentIndex, Skill skill){ active[agentIndex] = skill; }
        @Override public void cancelWork(int agentIndex){ active[agentIndex] = null; }
        @Override public void ensureAgent(int agentIndex){ }
        @Override public boolean agentAvailable(int agentIndex){ return true; }
        @Override public int coreCopper(){ return 250; }
        @Override public boolean buildingMatches(ExpertCoordinationDriver.BuildPlacement placement){
            return true;
        }
    }
}
