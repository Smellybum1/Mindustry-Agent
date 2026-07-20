package agentcore.task;

/**
 * A specific game entity (unit or building) addressed by its stable id.
 *
 * <p>The id is engine-independent here (a plain long). The engine adapter maps it
 * to the real entity handle when a skill executes the task.
 *
 * @param entityId stable entity id assigned by the environment
 */
public record EntityTarget(long entityId) implements Target{
    @Override public String describe(){
        return "entity #" + entityId;
    }
}
