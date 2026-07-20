package agentcore.skill;

/** Engine-neutral classification of one requested build footprint. */
public enum BuildTargetState{
    /** The footprint is empty and the requested block may be placed. */
    PLACEABLE,
    /** The engine is currently constructing the requested block for this team. */
    CONSTRUCTING,
    /** The requested block exists for this team and construction is complete. */
    COMPLETE,
    /** Another block/team occupies the footprint or placement is otherwise invalid. */
    OCCUPIED
}
