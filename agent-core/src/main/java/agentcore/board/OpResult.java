package agentcore.board;

import agentcore.event.CoordinationEvent;

/**
 * The outcome of a board operation (brief §15.4: "Invalid actions should not
 * crash the environment. They should have a small penalty and clear telemetry").
 * Rejections are returned, never thrown, so scripted and learned policies get a
 * uniform, action-maskable signal.
 *
 * @param ok     whether the operation was applied
 * @param reason machine-readable reason code; {@code "ok"} on success
 * @param event  the emitted event on success, or null on rejection
 */
public record OpResult(boolean ok, String reason, CoordinationEvent event){
    static OpResult ok(CoordinationEvent event){
        return new OpResult(true, "ok", event);
    }

    static OpResult rejected(String reason){
        return new OpResult(false, reason, null);
    }
}
