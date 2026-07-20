package agentcore.coordination;

import agentcore.skill.*;
import agentcore.task.*;
import org.junit.jupiter.api.*;

import java.util.*;

import static org.junit.jupiter.api.Assertions.*;

class ExpertCoordinationDriverTest{
    @Test
    void recordedSnapshotsProduceDecisionSequenceParity(){
        assertDoesNotThrow(() -> DecisionParityProbe.main(new String[0]));
    }

    @Test
    void greedyUtilitySelectsTheOpeningWorkByRole(){
        ExpertCoordinationDriver driver = new ExpertCoordinationDriver(plan(), new Port());
        driver.reset(7L);
        driver.startOpening(0L);

        List<ExpertCoordinationDriver.PolicyDecision> selections = driver.decisions().stream()
            .filter(decision -> decision.kind().equals("SELECT_TASK"))
            .toList();
        assertEquals("greedy-utility-expert-v1", driver.policyName());
        assertEquals(List.of("demo-line", "demo-defense", "demo-harvest"),
            selections.stream().map(ExpertCoordinationDriver.PolicyDecision::taskId).toList());
        assertEquals(3L, driver.decisions().stream()
            .filter(decision -> decision.kind().equals("UTILITY_SCORE")).count());
    }

    private static ExpertCoordinationPlan plan(){
        List<BuildSpec> line = List.of(new BuildSpec("mechanical-drill", 0, 0, 0));
        List<BuildSpec> defense = List.of(new BuildSpec("duo", 0, 0, 1));
        return new ExpertCoordinationPlan(
            24, 24, 8, 3, 8100,
            new ExpertCoordinationPlan.Schematic("line", 28, 28, 25, line),
            new ExpertCoordinationPlan.Schematic("defense", 32, 24, 100, defense),
            new ExpertCoordinationPlan.Schematic("fortification", 24, 24, 6,
                List.of(new BuildSpec("copper-wall", -2, 0, 0))),
            List.of(
                new ExpertCoordinationPlan.Schematic("expansion-1", 24, 24, 6,
                    List.of(new BuildSpec("copper-wall", 12, 0, 0))),
                new ExpertCoordinationPlan.Schematic("expansion-2", 24, 24, 6,
                    List.of(new BuildSpec("copper-wall", 15, 0, 0)))
            ),
            List.of(new TileTarget(28, 18), new TileTarget(31, 18),
                new TileTarget(28, 21)),
            List.of(new TileTarget(32, 23), new TileTarget(32, 25)),
            new ExpertCoordinationPlan.Region("east_lane", 26, 21, 21, 7),
            new ExpertCoordinationPlan.Region("defense_block", 30, 20, 6, 9),
            Map.of("copper-wall", 6, "duo", 35)
        );
    }

    private static final class Port implements ExpertCoordinationDriver.Port{
        private final Skill[] active = new Skill[3];

        @Override public SkillResult lastResult(int agentIndex){ return SkillResult.ready(); }
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
