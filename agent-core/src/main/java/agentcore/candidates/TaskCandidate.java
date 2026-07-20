package agentcore.candidates;

import agentcore.task.TaskSpec;

import java.nio.charset.StandardCharsets;
import java.util.Map;

/** One fixed-index candidate, its action mask, typed rejection reason, and utility. */
public record TaskCandidate(TaskSpec task, boolean valid, String invalidReason, double utility){
    public TaskCandidate{
        if(task == null) throw new IllegalArgumentException("task is required");
        invalidReason = valid ? "" : (invalidReason == null || invalidReason.isBlank()
            ? "invalid" : invalidReason);
    }

    /** Canonical byte rendering used by determinism tests and protocol adapters. */
    public byte[] canonicalBytes(){
        String target = task.target() == null ? "" : task.target().describe();
        StringBuilder cost = new StringBuilder();
        for(Map.Entry<String, Integer> entry : task.estimatedCost().asMap().entrySet()){
            if(cost.length() > 0) cost.append(',');
            cost.append(entry.getKey()).append('=').append(entry.getValue());
        }
        String line = task.taskId() + "|" + task.type().name() + "|" + target + "|"
            + Double.toHexString(task.priority()) + "|" + task.estimatedTicks() + "|"
            + cost + "|" + String.join(",", task.requiredCapabilities()) + "|"
            + task.helpersRequested() + "|" + task.exclusive() + "|"
            + (task.parentTaskId() == null ? "" : task.parentTaskId()) + "|"
            + String.join(",", task.dependencyTaskIds()) + "|" + valid + "|"
            + invalidReason + "|" + Double.toHexString(utility);
        return line.getBytes(StandardCharsets.UTF_8);
    }
}
