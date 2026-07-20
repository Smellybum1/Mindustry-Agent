package agentcore;

import java.util.Objects;

/**
 * Stable identity for a single cooperating agent within one environment (brief §9).
 *
 * <p>An agent identity is stable across episode resets within a JVM: {@link #index}
 * is a dense 0-based slot used for fixed-width observations and action bundles,
 * while {@link #displayName} is the human-facing handle used only when rendering
 * announcements (e.g. {@code agent-copper}). Equality and hashing are by index so
 * that the same slot maps to the same agent regardless of display name.
 *
 * @param index       dense 0-based agent slot, unique within an environment
 * @param displayName human-readable handle for announcements; never authoritative
 */
public record AgentId(int index, String displayName){
    public AgentId{
        if(index < 0){
            throw new IllegalArgumentException("agent index must be non-negative, got " + index);
        }
        displayName = (displayName == null || displayName.isBlank())
            ? "agent-" + index
            : displayName;
    }

    /** Convenience factory generating a default display name from the index. */
    public static AgentId of(int index){
        return new AgentId(index, "agent-" + index);
    }

    @Override public boolean equals(Object o){
        if(this == o) return true;
        if(!(o instanceof AgentId other)) return false;
        return index == other.index;
    }

    @Override public int hashCode(){
        return Objects.hash(index);
    }
}
