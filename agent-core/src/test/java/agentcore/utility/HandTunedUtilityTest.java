package agentcore.utility;

import agentcore.AgentId;
import agentcore.TaskType;
import agentcore.task.TaskSpec;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.*;

/**
 * Tests the additive hand-tuned utility (brief §11.1): weighted sum of feature
 * terms, sign handling for cost terms, and determinism.
 */
class HandTunedUtilityTest{

    private static final AgentId A = new AgentId(0, "agent-a");
    private static final TaskSpec TASK = TaskSpec.builder("t", TaskType.BUILD_LINE).build();

    @Test void additiveWeightedSumWithCostSubtraction(){
        UtilityFeatures f = UtilityFeatures.builder()
            .teamValue(2.0)          // *1.0  = +2.0
            .urgency(1.0)            // *1.0  = +1.0
            .duplicationRisk(0.5)    // *1.0  = -0.5
            .switchingCost(1.0)      // *0.5  = -0.5
            .build();
        HandTunedUtility u = new HandTunedUtility((agent, task, tick) -> f);

        double score = u.score(A, TASK, 0);
        assertEquals(2.0, score, 1e-9);

        UtilityBreakdown bd = u.breakdown(A, TASK, 0);
        assertEquals(2.0, bd.teamValue(), 1e-9);
        assertEquals(1.0, bd.urgency(), 1e-9);
        assertEquals(-0.5, bd.duplicationRisk(), 1e-9);
        assertEquals(-0.5, bd.switchingCost(), 1e-9);
        assertEquals(score, bd.total(), 1e-9);
    }

    @Test void humanPriorityDominatesByDefault(){
        UtilityFeatures human = UtilityFeatures.builder().humanPriority(1.0).build();
        UtilityFeatures team = UtilityFeatures.builder().teamValue(1.0).build();
        HandTunedUtility uh = new HandTunedUtility((a, t, tick) -> human);
        HandTunedUtility ut = new HandTunedUtility((a, t, tick) -> team);
        // Default humanPriority weight (2.0) outranks teamValue weight (1.0).
        assertTrue(uh.score(A, TASK, 0) > ut.score(A, TASK, 0));
    }

    @Test void emptyFeaturesScoreZero(){
        HandTunedUtility u = new HandTunedUtility((a, t, tick) -> UtilityFeatures.builder().build());
        assertEquals(0.0, u.score(A, TASK, 0), 1e-9);
    }

    @Test void deterministicAcrossRepeatedCalls(){
        UtilityFeatures f = UtilityFeatures.builder().teamValue(1.5).proximity(0.7).danger(0.3).build();
        HandTunedUtility u = new HandTunedUtility((a, t, tick) -> f);
        double first = u.score(A, TASK, 0);
        for(int i = 0; i < 100; i++){
            assertEquals(first, u.score(A, TASK, i % 3), 0.0);
        }
    }

    @Test void customWeightsAreApplied(){
        UtilityFeatures f = UtilityFeatures.builder().teamValue(3.0).build();
        UtilityWeights w = UtilityWeights.builder().teamValue(2.0).build();
        HandTunedUtility u = new HandTunedUtility((a, t, tick) -> f, w);
        assertEquals(6.0, u.score(A, TASK, 0), 1e-9);
    }
}
