package agentcore.candidates;

/** Immutable evidence for the BUILD_LINE working-economy predicate. */
public record EconomySnapshot(
    boolean blocksComplete,
    boolean conveyorConnected,
    double coreInflowPerSecond,
    double requiredInflowPerSecond,
    int sampleTicks,
    int requiredSampleTicks
){
    public EconomySnapshot{
        if(!Double.isFinite(coreInflowPerSecond) || coreInflowPerSecond < 0.0
            || !Double.isFinite(requiredInflowPerSecond) || requiredInflowPerSecond < 0.0
            || sampleTicks < 0 || requiredSampleTicks <= 0){
            throw new IllegalArgumentException("invalid economy evidence");
        }
    }

    public boolean operational(){
        return blocksComplete && conveyorConnected && sampleTicks >= requiredSampleTicks
            && coreInflowPerSecond + 1e-9 >= requiredInflowPerSecond;
    }

    public double readiness(){
        double block = blocksComplete ? 1.0 : 0.0;
        double path = conveyorConnected ? 1.0 : 0.0;
        double sample = Math.min(1.0, sampleTicks / (double)requiredSampleTicks);
        double inflow = requiredInflowPerSecond == 0.0 ? 1.0
            : Math.min(1.0, coreInflowPerSecond / requiredInflowPerSecond);
        return Math.min(Math.min(block, path), Math.min(sample, inflow));
    }
}
