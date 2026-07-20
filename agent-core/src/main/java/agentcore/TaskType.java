package agentcore;

/**
 * The initial, deliberately small typed task vocabulary (brief §10.2).
 *
 * <p>Each task type will eventually define its schema, valid targets,
 * preconditions, required capabilities, resource estimate, candidate-generation
 * logic, progress function, completion predicate, failure conditions, timeout,
 * cancellation/cleanup, reservation requirements, message templates, reward
 * eligibility, and tests. Not all types are implemented in the first milestone;
 * this enum only fixes the vocabulary and its ordinal identity for the protocol.
 */
public enum TaskType{
    HARVEST_RESOURCE,
    DELIVER_RESOURCE,
    BUILD_SCHEMATIC,
    BUILD_LINE,
    SUPPLY_BUILDING,
    SUPPLY_TURRET,
    REPAIR_REGION,
    DEFEND_REGION,
    ATTACK_TARGET,
    SCOUT_REGION,
    ESCORT_AGENT,
    ASSIST_BUILD,
    CLEAR_OBSTACLE,
    GENERATE_POWER,
    WAIT,
    REQUEST_HELP
}
