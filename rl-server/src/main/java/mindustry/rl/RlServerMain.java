package mindustry.rl;

import arc.util.*;

import java.io.*;
import java.net.*;
import java.time.*;
import java.time.format.*;

/**
 * Entry point for the externally-stepped headless RL launcher (roadmap M1).
 *
 * <p>Initializes Mindustry content headlessly, then serves a single loopback client
 * over the length-prefixed JSON protocol (docs/PROTOCOL.md): handshake, reset, step N
 * ticks at fixed {@code 1/60 s} delta, minimal observation, deterministic state hash.
 *
 * <p>Usage: {@code java -jar rl-server.jar [--port <N>]} (default port 47810). Binds
 * {@code 127.0.0.1} only. Prints exactly one {@code READY <port>} line to stdout when
 * listening; all engine/diagnostic logs are routed to stderr so stdout stays clean for
 * launcher readiness detection.
 *
 * <p>Threading invariant (AGENTS.md §3): only the simulation thread (this {@code main})
 * reads or mutates game state; the socket reader thread only parses and queues requests.
 */
public final class RlServerMain{
    public static final String ENGINE_TAG = RlServer.ENGINE_TAG;
    public static final String ENGINE_COMMIT = RlServer.ENGINE_COMMIT;
    public static final int PROTOCOL_VERSION = RlServer.PROTOCOL_VERSION;

    private static final int DEFAULT_PORT = 47810;

    private RlServerMain(){
    }

    public static void main(String[] args){
        int port = DEFAULT_PORT;
        for(int i = 0; i < args.length; i++){
            if(args[i].equals("--port") && i + 1 < args.length){
                port = Integer.parseInt(args[++i]);
            }else if(args[i].startsWith("--port=")){
                port = Integer.parseInt(args[i].substring("--port=".length()));
            }
        }

        //route ALL Mindustry logging to stderr — stdout is reserved for the READY line
        Log.useColors = false;
        DateTimeFormatter fmt = DateTimeFormatter.ofPattern("HH:mm:ss");
        Log.logger = (level, text) -> System.err.println(
            "[" + LocalDateTime.now().format(fmt) + "] [" + level + "] " + Log.formatColors(text, false));

        RlServer server = new RlServer(port);
        try{
            server.boot();
        }catch(Throwable t){
            System.err.println("rl-server boot failed: " + t);
            t.printStackTrace();
            System.exit(2);
        }

        try{
            server.serve();
        }catch(BindException e){
            System.err.println("rl-server: cannot bind 127.0.0.1:" + port + " (port busy): " + e.getMessage());
            System.exit(3);
        }catch(IOException e){
            System.err.println("rl-server: I/O error: " + e.getMessage());
            System.exit(4);
        }catch(Throwable t){
            System.err.println("rl-server: fatal: " + t);
            t.printStackTrace();
            System.exit(5);
        }

        System.exit(0);
    }
}
