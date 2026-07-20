package mindustry.agentplugin;

import agentcore.AgentId;

/**
 * Placeholder for the real-time dedicated-server demonstration adapter
 * (roadmap M6/M10). See agent-plugin/README.md.
 *
 * <p>The real implementation will extend Mindustry's server {@code Plugin} type,
 * register server-controlled agent units, and drive them through {@code agent-core}
 * skills at real-time pacing while a human plays on the same private server. It is
 * intentionally not wired as a loadable plugin yet (no {@code plugin.json}) so that
 * the demo path is only built once training-mode behaviour exists to reuse.
 */
public final class AgentPlugin{
    private AgentPlugin(){
    }

    /**
     * Trivial reference to {@link AgentId} so the {@code :agent-core} dependency
     * edge is exercised at compile time. Replaced by real registration logic.
     */
    public static String describe(){
        return "agent-plugin stub not yet implemented (roadmap M6/M10); "
            + "example agent id " + AgentId.of(0).displayName();
    }
}
