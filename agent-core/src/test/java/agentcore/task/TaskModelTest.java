package agentcore.task;

import agentcore.TaskType;
import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Map;
import java.util.Set;

import static org.junit.jupiter.api.Assertions.*;

/** Tests the immutable task model: builder defaults, deterministic ordering, targets. */
class TaskModelTest{

    @Test void builderDefaultsAndImmutability(){
        TaskSpec s = TaskSpec.builder("t", TaskType.BUILD_LINE).build();
        assertEquals("t", s.taskId());
        assertEquals(TaskType.BUILD_LINE, s.type());
        assertTrue(s.exclusive());
        assertEquals(0, s.helpersRequested());
        assertTrue(s.estimatedCost().isEmpty());
        assertEquals(TaskOrigin.AUTONOMOUS, s.origin());
        assertNull(s.sourceGoalId());
        assertThrows(UnsupportedOperationException.class, () -> s.dependencyTaskIds().add("x"));
    }

    @Test void requiredCapabilitiesAreSortedAndCopied(){
        TaskSpec s = TaskSpec.builder("t", TaskType.SUPPLY_TURRET)
            .requiredCapabilities(Set.of("carry:copper", "build", "aim"))
            .build();
        assertEquals(List.of("aim", "build", "carry:copper"), List.copyOf(s.requiredCapabilities()));
    }

    @Test void resourceCostIsOrderedAndDropsZeros(){
        ResourceCost c = ResourceCost.of(Map.of("lead", 5, "copper", 10, "sand", 0));
        assertEquals(List.of("copper", "lead"), List.copyOf(c.asMap().keySet()));
        assertEquals(10, c.amount("copper"));
        assertEquals(0, c.amount("sand"));
    }

    @Test void targetsDescribeDeterministically(){
        assertEquals("tile (35, 18)", new TileTarget(35, 18).describe());
        assertEquals("region east-defense", new RegionTarget("east-defense").describe());
        assertEquals("entity #42", new EntityTarget(42).describe());
        assertEquals("120 copper", new ResourceTarget("copper", 120).describe());
    }

    @Test void negativeAmountsRejected(){
        assertThrows(IllegalArgumentException.class, () -> new ResourceTarget("copper", -1));
        assertThrows(IllegalArgumentException.class, () -> ResourceCost.of("copper", -5));
        assertThrows(IllegalArgumentException.class,
            () -> TaskSpec.builder("t", TaskType.WAIT).helpersRequested(-1).build());
    }

    @Test void humanOriginRequiresAStableSourceGoal(){
        TaskSpec human = TaskSpec.builder("human:goal:1", TaskType.DEFEND_REGION)
            .humanOrigin("human:goal:1").build();
        assertEquals(TaskOrigin.HUMAN, human.origin());
        assertEquals("human:goal:1", human.sourceGoalId());
        assertThrows(NullPointerException.class, () ->
            TaskSpec.builder("bad", TaskType.WAIT).humanOrigin(null));
        assertThrows(IllegalArgumentException.class, () ->
            TaskSpec.builder("bad", TaskType.WAIT).humanOrigin("not-a-goal").build());
        assertThrows(IllegalArgumentException.class, () ->
            TaskSpec.builder("different", TaskType.WAIT).humanOrigin("human:goal:1").build());
    }
}
