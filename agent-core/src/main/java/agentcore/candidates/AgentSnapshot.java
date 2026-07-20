package agentcore.candidates;

import agentcore.AgentId;

import java.util.Collections;
import java.util.LinkedHashSet;
import java.util.Set;
import java.util.TreeSet;

/** Immutable per-boundary agent facts used to mask candidate tasks. */
public record AgentSnapshot(
    AgentId id,
    float worldX,
    float worldY,
    float assignmentRange,
    Set<String> capabilities
){
    public AgentSnapshot{
        if(id == null) throw new IllegalArgumentException("id is required");
        if(!Float.isFinite(worldX) || !Float.isFinite(worldY)){
            throw new IllegalArgumentException("agent coordinates must be finite");
        }
        if(!Float.isFinite(assignmentRange) || assignmentRange < 0f){
            throw new IllegalArgumentException("assignmentRange must be finite and >= 0");
        }
        capabilities = Collections.unmodifiableSet(
            new LinkedHashSet<>(new TreeSet<>(capabilities == null ? Set.of() : capabilities)));
    }

    public boolean hasCapabilities(Set<String> required){
        return capabilities.containsAll(required);
    }
}
