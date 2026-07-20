package mindustry.rl;

import arc.struct.*;
import mindustry.game.*;
import mindustry.gen.*;
import mindustry.type.*;
import mindustry.world.blocks.storage.CoreBlock.*;

import java.io.*;
import java.security.*;
import java.util.*;

import static mindustry.Vars.*;

/**
 * Canonical, history-independent state hash (docs/ENGINE_NOTES.md §10).
 *
 * <p>Algorithm: SHA-256 over a deterministically ordered byte stream. Entities are
 * <b>sorted by id</b> before hashing because {@code EntityGroup} iteration order is
 * swap-remove / history dependent. Floating-point quantities (positions, health) are
 * quantized by rounding {@code value * 1000} to a {@code long} — i.e. precision
 * <b>1e-3</b> — before hashing, so bit-level FP jitter cannot change the hash while
 * meaningful state differences still do. Absolute entity ids are hashed only after
 * {@code EntityGroup.lastId} is reset per episode (see {@link RlServer}), so identical
 * scenarios across episodes/JVMs produce identical hashes.
 *
 * <p>Inputs: {@code state.tick}, {@code state.wave}, per-core team + item counts, all
 * buildings (sorted by id: block/team/quantized pos/health), all units (sorted by id:
 * type/team/quantized pos/health). Never includes {@code Fx}/render/{@code Time.millis}.
 */
public final class StateHasher{
    private static final long QUANT = 1000L; //1e-3 precision

    private StateHasher(){}

    public static String hash(){
        return hash(null);
    }

    public static String hash(RlAgentRegistry registry){
        try{
            MessageDigest md = MessageDigest.getInstance("SHA-256");
            DataOutputStream out = new DataOutputStream(new DigestOutputStream(md));

            //tick is a double advanced by exactly +1.0 per update; hash the exact bits
            out.writeLong(Double.doubleToLongBits(state.tick));
            out.writeInt(state.wave);
            //scenario wave counters: wavetime decrements by the fixed delta (bit-exact), and
            //the live wave-team unit count. Both deterministic; they fingerprint the wave phase.
            out.writeInt(Float.floatToIntBits(state.wavetime));
            out.writeInt(state.enemies);
            out.writeBoolean(state.gameOver);

            //cores, sorted by team id for stability
            Seq<CoreBuild> cores = new Seq<>();
            for(Teams.TeamData td : state.teams.getActive()){
                cores.addAll(td.cores);
            }
            cores.sort(Comparator.comparingInt(c -> c.id()));
            out.writeInt(cores.size);
            for(CoreBuild core : cores){
                out.writeInt(core.team().id);
                writeItems(out, core.items);
            }

            //buildings, sorted by id
            Seq<Building> builds = new Seq<>();
            for(Building b : Groups.build){
                builds.add(b);
            }
            builds.sort(Comparator.comparingInt(b -> b.id()));
            out.writeInt(builds.size);
            for(Building b : builds){
                out.writeInt(b.id());
                out.writeInt(b.block.id);
                out.writeInt(b.team().id);
                out.writeLong(quant(b.x));
                out.writeLong(quant(b.y));
                out.writeLong(quant(b.health));
            }

            //units, sorted by id (none in M1, but future-proof and part of the canon)
            Seq<Unit> units = new Seq<>();
            for(Unit u : Groups.unit){
                units.add(u);
            }
            units.sort(Comparator.comparingInt(u -> u.id()));
            out.writeInt(units.size);
            for(Unit u : units){
                out.writeInt(u.id());
                out.writeInt(u.type == null ? -1 : u.type.id);
                out.writeInt(u.team().id);
                out.writeLong(quant(u.x));
                out.writeLong(quant(u.y));
                out.writeLong(quant(u.vel().x));
                out.writeLong(quant(u.vel().y));
                out.writeLong(quant(u.health));
                //cargo: agent units carry mined ore — part of the canonical fingerprint (D7)
                Item carried = u.item();
                if(carried != null){
                    out.writeInt(carried.id);
                    out.writeInt(u.stack().amount);
                }else{
                    out.writeInt(-1);
                    out.writeInt(0);
                }
            }

            //agent registry + active skill state (D7): golden replays break if a skill
            //state machine changes behaviour. Iterated in dense index order (deterministic).
            if(registry != null){
                out.writeInt(registry.size());
                for(RlAgentRegistry.Agent agent : registry.agents()){
                    out.writeInt(agent.index);
                    out.writeInt(agent.unit.id());
                    byte[] typeBytes = agent.controller.activeType()
                        .getBytes(java.nio.charset.StandardCharsets.UTF_8);
                    out.writeInt(typeBytes.length);
                    out.write(typeBytes);
                    var result = agent.controller.lastResult();
                    out.writeInt(result.status().ordinal());
                    out.writeInt(result.reason().ordinal());
                    out.writeLong(quant(result.progress()));
                }
            }else{
                out.writeInt(0);
            }

            out.flush();
            return toHex(md.digest());
        }catch(Exception e){
            throw new RuntimeException("state hash failed", e);
        }
    }

    private static void writeItems(DataOutputStream out, mindustry.world.modules.ItemModule items) throws IOException{
        //hash every item slot in content order for a full inventory fingerprint
        Seq<Item> all = mindustry.Vars.content.items();
        out.writeInt(all.size);
        for(Item item : all){
            out.writeInt(items == null ? 0 : items.get(item));
        }
    }

    private static long quant(float v){
        return Math.round((double)v * QUANT);
    }

    private static String toHex(byte[] bytes){
        StringBuilder sb = new StringBuilder(bytes.length * 2);
        for(byte b : bytes){
            sb.append(Character.forDigit((b >> 4) & 0xf, 16));
            sb.append(Character.forDigit(b & 0xf, 16));
        }
        return sb.toString();
    }

    /** OutputStream that feeds a MessageDigest (avoids buffering the whole stream). */
    private static final class DigestOutputStream extends OutputStream{
        private final MessageDigest md;
        DigestOutputStream(MessageDigest md){ this.md = md; }
        @Override public void write(int b){ md.update((byte)b); }
        @Override public void write(byte[] b, int off, int len){ md.update(b, off, len); }
    }

    /** Copper/lead helper used by the observation payload. */
    public static int coreItem(Item item){
        CoreBuild core = Team.sharded.core();
        return core == null ? 0 : core.items.get(item);
    }
}
