package mindustry.rl;

/**
 * Placeholder entry point for the externally-stepped headless RL launcher.
 *
 * <p>The real launcher (roadmap M1) will initialize Mindustry content in headless
 * mode, replace the free-running wall-clock loop with an externally controlled
 * fixed-step loop (1 engine update == 1 game tick at delta 1/60 s, see ADR-0002),
 * load scenarios, reset episodes in-process, apply agent action bundles atomically
 * at decision boundaries, advance an exact number of ticks, extract observations
 * and rewards, and return deterministic state hashes over the length-prefixed JSON
 * protocol described in {@code docs/PROTOCOL.md}.
 *
 * <p>Threading invariant (see AGENTS.md §3): only the simulation thread may read
 * or mutate game state. I/O threads may only parse and queue requests.
 *
 * <p>For now this main prints the pinned engine identity and exits 0.
 */
public final class RlServerMain{
    /** Pinned engine tag; kept in sync with {@code ENGINE_VERSION}. */
    public static final String ENGINE_TAG = "v159.7";
    /** Pinned engine commit; kept in sync with {@code ENGINE_VERSION}. */
    public static final String ENGINE_COMMIT = "c9686eb5d0ae5dd47ee02c40f99f7d5018ccbc8c";
    /** Bootstrap-phase protocol version (see docs/PROTOCOL.md). */
    public static final int PROTOCOL_VERSION = 1;

    private RlServerMain(){
    }

    public static void main(String[] args){
        System.out.println("engine_tag=" + ENGINE_TAG);
        System.out.println("engine_commit=" + ENGINE_COMMIT);
        System.out.println("protocol_version=" + PROTOCOL_VERSION);
        System.out.println("rl-server spike not yet implemented (roadmap M1)");
        System.exit(0);
    }
}
