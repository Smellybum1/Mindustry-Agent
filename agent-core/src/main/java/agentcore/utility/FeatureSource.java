package agentcore.utility;

import agentcore.AgentId;
import agentcore.task.TaskSpec;

/**
 * Supplies the raw {@link UtilityFeatures} for an {@code (agent, task)} pair at a
 * given tick (brief §11.1). This is the single seam through which engine-derived
 * signals (proximity, travel cost, danger, duplication risk, ...) enter the
 * otherwise headless utility scaffold. The engine adapter provides a real
 * implementation later; tests and scripted policies can supply a fixed one.
 *
 * <p>Implementations must be deterministic: the same inputs must yield the same
 * features (brief §7.5).
 */
@FunctionalInterface
public interface FeatureSource{
    UtilityFeatures featuresFor(AgentId agent, TaskSpec task, long tick);
}
