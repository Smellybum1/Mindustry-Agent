package agentcore.announce;

import agentcore.AgentId;
import agentcore.CoordinationAct;
import agentcore.TaskType;
import agentcore.event.CoordinationEvent;
import agentcore.task.TaskStatus;

import java.util.ArrayList;
import java.util.List;

/**
 * Renders deterministic, human-readable announcement lines from
 * {@link CoordinationEvent}s (brief §20.3). Structured communication is
 * authoritative; these strings are <em>rendered from</em> the structure and never
 * the reverse (ADR-0005). There is no randomness and no wall-clock — the same
 * event always renders the same string.
 *
 * <p>Templates are keyed by {@link CoordinationAct} and specialized per
 * {@link TaskType} through {@link #phrase}, with a generic fallback for any
 * unhandled combination. Examples (brief §20.3):
 *
 * <pre>
 * [Agent Copper] Starting: establish copper line to the core.
 * [Agent Shield] Starting: build east defence. Requesting 1 helper.
 * [Agent Relay] Helping Shield: deliver 120 copper.
 * [Agent Shield] Blocked: 18 copper short. Waiting up to 20 seconds.
 * [Agent Copper] Complete: copper line active at 4.2 items/sec.
 * </pre>
 *
 * <p>This renderer produces lines in that style; exact scenario-specific wording
 * (e.g. "at 4.2 items/sec") is supplied by callers through reason codes and
 * targets, keeping the renderer purely structural.
 */
public final class AnnouncementRenderer{

    /** Render one event to its announcement line. Never returns null. */
    public String render(CoordinationEvent ev){
        if(ev.act() == null){
            return renderBoardEvent(ev);
        }
        return switch(ev.act()){
            case ANNOUNCE_INTENT -> agentPrefix(ev.agent()) + "Intending: " + phrase(ev) + helperSuffix(ev) + ".";
            case CLAIM_TASK      -> agentPrefix(ev.agent()) + "Claiming: " + phrase(ev) + ".";
            case START_TASK      -> agentPrefix(ev.agent()) + "Starting: " + phrase(ev) + helperSuffix(ev) + ".";
            case OFFER_HELP      -> agentPrefix(ev.agent()) + "Offering to help " + name(ev.relatedAgent())
                                        + ": " + contribution(ev) + ".";
            case ACCEPT_HELP     -> agentPrefix(ev.agent()) + "Helping " + name(ev.relatedAgent())
                                        + ": " + contribution(ev) + ".";
            case DECLINE_HELP    -> agentPrefix(ev.agent()) + "Declining help from " + name(ev.relatedAgent()) + ".";
            case REQUEST_HELP    -> agentPrefix(ev.agent()) + "Requesting " + helperCount(ev)
                                        + ": " + phrase(ev) + ".";
            case BLOCKED         -> agentPrefix(ev.agent()) + "Blocked: " + blockedDetail(ev);
            case PROGRESS        -> agentPrefix(ev.agent()) + "Progress: " + phrase(ev)
                                        + " (" + percent(ev.progress()) + ").";
            case HEARTBEAT       -> agentPrefix(ev.agent()) + "Working: " + phrase(ev) + ".";
            case COMPLETE        -> agentPrefix(ev.agent()) + "Complete: " + phrase(ev) + ".";
            case ABANDON         -> agentPrefix(ev.agent()) + "Abandoning: " + phrase(ev)
                                        + reasonSuffix(ev) + ".";
            case RELEASE         -> agentPrefix(ev.agent()) + "Releasing: " + phrase(ev) + ".";
        };
    }

    /** Render only the events flagged for human announcement, in order. */
    public List<String> renderAnnouncements(List<CoordinationEvent> events){
        List<String> out = new ArrayList<>();
        for(CoordinationEvent ev : events){
            if(ev.announce()) out.add(render(ev));
        }
        return out;
    }

    // ---- board-internal (null act) events ----

    private String renderBoardEvent(CoordinationEvent ev){
        if("yield_to_human".equals(ev.reasonCode())){
            return agentPrefix(ev.agent()) + "Yielding to human: " + safe(ev.targetDescription()) + ".";
        }
        if("reservation_overlap".equals(ev.reasonCode())){
            return agentPrefix(ev.agent()) + "Reservation conflict: " + safe(ev.targetDescription()) + ".";
        }
        if(ev.toStatus() == TaskStatus.EXPIRED){
            return "[Board] Expired: " + phrase(ev) + " (lease lapsed).";
        }
        if(ev.toStatus() == TaskStatus.OPEN && ev.fromStatus() == null){
            return "[Board] Proposed: " + phrase(ev) + ".";
        }
        return "[Board] " + safe(ev.taskId()) + ": " + ev.fromStatus() + " -> " + ev.toStatus() + ".";
    }

    // ---- phrasing ----

    private String phrase(CoordinationEvent ev){
        TaskType type = ev.taskType();
        String target = ev.targetDescription();
        if(type == null) return safe(ev.taskId());
        String at = target == null ? "" : " at " + target;
        String to = target == null ? "" : " to " + target;
        String of = target == null ? "" : " " + target;
        return switch(type){
            case HARVEST_RESOURCE -> "harvest" + of;
            case DELIVER_RESOURCE -> "deliver" + of;
            case BUILD_SCHEMATIC  -> "build schematic" + at;
            case BUILD_LINE       -> "establish production line" + at;
            case SUPPLY_BUILDING  -> "supply building" + at;
            case SUPPLY_TURRET    -> "supply turret" + at;
            case REPAIR_REGION    -> "repair" + of;
            case DEFEND_REGION    -> "defend" + of;
            case ATTACK_TARGET    -> "attack" + of;
            case SCOUT_REGION     -> "scout" + of;
            case ESCORT_AGENT     -> "escort" + of;
            case ASSIST_BUILD     -> "assist build" + at;
            case CLEAR_OBSTACLE   -> "clear obstacle" + at;
            case GENERATE_POWER   -> "generate power" + at;
            case WAIT             -> "wait";
            case REQUEST_HELP     -> "request help";
        };
    }

    private String helperSuffix(CoordinationEvent ev){
        int n = ev.helpersRequested();
        if(n <= 0) return "";
        return ". Requesting " + n + " helper" + (n == 1 ? "" : "s");
    }

    private String helperCount(CoordinationEvent ev){
        int n = Math.max(1, ev.helpersRequested());
        return n + " helper" + (n == 1 ? "" : "s");
    }

    private String contribution(CoordinationEvent ev){
        return safe(ev.offeredContribution());
    }

    private String blockedDetail(CoordinationEvent ev){
        return ev.reasonCode() != null ? ev.reasonCode() : phrase(ev);
    }

    private String reasonSuffix(CoordinationEvent ev){
        return ev.reasonCode() != null ? " (" + ev.reasonCode() + ")" : "";
    }

    private String percent(double progress){
        long pct = Math.round(progress * 100);
        return pct + "%";
    }

    // ---- names ----

    private String agentPrefix(AgentId agent){
        return "[Agent " + name(agent) + "] ";
    }

    /** Prettify a display name for announcements: {@code agent-copper} -> {@code Copper}. */
    private String name(AgentId agent){
        if(agent == null) return "the team";
        String dn = agent.displayName();
        String core = dn;
        if(core.regionMatches(true, 0, "agent-", 0, 6)){
            core = core.substring(6);
        }
        if(core.isEmpty()) return dn;
        return Character.toUpperCase(core.charAt(0)) + core.substring(1);
    }

    private String safe(String s){
        return s == null ? "" : s;
    }
}
