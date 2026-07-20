package agentcore.candidates;

import java.util.*;

/** One scenario-derived expert schematic exposed through the general task catalog. */
public record PlannedSchematicSnapshot(
    String taskId,
    String schematicId,
    int anchorX,
    int anchorY,
    int copperCost,
    boolean complete,
    int minimumWave,
    double priority,
    List<String> dependencyTaskIds
){
    public PlannedSchematicSnapshot{
        if(taskId == null || taskId.isBlank()) throw new IllegalArgumentException("taskId required");
        if(schematicId == null || schematicId.isBlank()){
            throw new IllegalArgumentException("schematicId required");
        }
        if(copperCost < 0 || minimumWave < 1){
            throw new IllegalArgumentException("invalid schematic cost/wave");
        }
        dependencyTaskIds = List.copyOf(dependencyTaskIds == null
            ? List.of() : dependencyTaskIds);
    }
}
