package mindustry.rl;

import agentcore.skill.*;
import arc.util.serialization.*;
import mindustry.type.*;
import mindustry.world.*;

import static mindustry.Vars.*;

/**
 * Decodes protocol {@code agent_actions} command objects into {@link Skill}s and applies
 * them to the registry on the simulation thread (docs/M3_DESIGN.md D5).
 *
 * <p>Every action is validated; an invalid one yields {@code accepted=false} with a reason
 * code in the {@code action_results[]} entry and <b>never</b> throws. Command types:
 * {@code NAVIGATE}, {@code MINE}, {@code DELIVER_CORE}, {@code WAIT}, {@code BUILD},
 * {@code SCHEMATIC}, {@code SUPPLY}, {@code REBUILD}, and {@code CONTINUE} (or an absent command)
 * which keeps the current skill running.
 *
 * <p>Well-formedness (finite numbers, in-bounds tiles) is checked here; semantic
 * conditions such as a tile not actually being ore surface as a {@code BLOCKED} skill
 * status at execution time (see {@link MineResource}), not a decode rejection.
 */
final class ActionDecoder{
    static final float DEFAULT_NAV_TOLERANCE = 8f;
    static final int DEFAULT_MINE_AMOUNT = 20;
    static final long DEFAULT_WAIT_TICKS = 60L;

    private ActionDecoder(){}

    /** Apply one {@code {agent_id, command}} action, returning its result object. */
    static Jval apply(AgentRuntimeRegistry registry, Scenario scenario, Jval action){
        int agentId = action.getInt("agent_id", -1);
        AgentRuntimeRegistry.Agent agent = registry.get(agentId);
        if(agent == null){
            return result(agentId, false, "unknown_agent", "");
        }

        Jval command = action.get("command");
        if(command == null || command.isNull()){
            return result(agentId, true, "continue", agent.controller().activeType());
        }
        String type = command.getString("type", "");

        switch(type){
            case "":
            case "CONTINUE":
                return result(agentId, true, "continue", agent.controller().activeType());

            case "NAVIGATE":{
                float x = (float)command.getDouble("x", Double.NaN);
                float y = (float)command.getDouble("y", Double.NaN);
                float tol = (float)command.getDouble("tolerance", DEFAULT_NAV_TOLERANCE);
                if(!finite(x) || !finite(y)){
                    return result(agentId, false, "malformed", type);
                }
                agent.controller().setSkill(new NavigateTo(x, y, Math.max(0f, tol)));
                return result(agentId, true, "accepted", type);
            }

            case "MINE":{
                int tx = command.getInt("tile_x", Integer.MIN_VALUE);
                int ty = command.getInt("tile_y", Integer.MIN_VALUE);
                int amount = command.getInt("amount", DEFAULT_MINE_AMOUNT);
                if(!inBounds(tx, ty)){
                    return result(agentId, false, "out_of_bounds", type);
                }
                if(amount <= 0){
                    return result(agentId, false, "malformed", type);
                }
                agent.controller().setSkill(new MineResource(tx, ty, amount));
                return result(agentId, true, "accepted", type);
            }

            case "DELIVER_CORE":
                agent.controller().setSkill(new DeliverToCore());
                return result(agentId, true, "accepted", type);

            case "WAIT":{
                long ticks = command.getLong("ticks", DEFAULT_WAIT_TICKS);
                if(ticks < 0){
                    return result(agentId, false, "malformed", type);
                }
                agent.controller().setSkill(new Wait(ticks));
                return result(agentId, true, "accepted", type);
            }

            case "BUILD":{
                String blockName = command.getString("block", "");
                int tx = command.getInt("tile_x", Integer.MIN_VALUE);
                int ty = command.getInt("tile_y", Integer.MIN_VALUE);
                int rotation = command.getInt("rotation", 0);
                if(!inBounds(tx, ty)){
                    return result(agentId, false, "out_of_bounds", type);
                }
                if(rotation < 0 || rotation > 3){
                    return result(agentId, false, "malformed", type);
                }
                Block block = content.block(blockName);
                if(block == null || !state.rules.researched.contains(block)){
                    return result(agentId, false, "block_not_allowed", type);
                }
                agent.controller().setSkill(new BuildBlock(block.name, tx, ty, rotation));
                return result(agentId, true, "accepted", type);
            }

            case "SCHEMATIC":{
                String name = command.getString("name", "");
                int anchorX = command.getInt("tile_x", Integer.MIN_VALUE);
                int anchorY = command.getInt("tile_y", Integer.MIN_VALUE);
                Scenario.SchematicSpec spec = scenario.schematic(name);
                if(spec == null){
                    return result(agentId, false, "unknown_schematic", type);
                }
                for(BuildSpec block : spec.blocks()){
                    if(!inBounds(anchorX + block.offsetX(), anchorY + block.offsetY())){
                        return result(agentId, false, "out_of_bounds", type);
                    }
                }
                agent.controller().setSkill(new ExecuteSchematic(name, anchorX, anchorY, spec.blocks()));
                return result(agentId, true, "accepted", type);
            }

            case "SUPPLY":{
                String itemName = command.getString("item", "");
                int tx = command.getInt("tile_x", Integer.MIN_VALUE);
                int ty = command.getInt("tile_y", Integer.MIN_VALUE);
                int amount = command.getInt("amount", 0);
                Item item = content.item(itemName);
                if(!inBounds(tx, ty)){
                    return result(agentId, false, "out_of_bounds", type);
                }
                if(item == null || amount <= 0){
                    return result(agentId, false, "malformed", type);
                }
                agent.controller().setSkill(new SupplyBuilding(item.name, tx, ty, amount));
                return result(agentId, true, "accepted", type);
            }

            case "REBUILD":{
                int x1 = command.getInt("x1", Integer.MIN_VALUE);
                int y1 = command.getInt("y1", Integer.MIN_VALUE);
                int x2 = command.getInt("x2", Integer.MIN_VALUE);
                int y2 = command.getInt("y2", Integer.MIN_VALUE);
                if(!inBounds(x1, y1) || !inBounds(x2, y2)){
                    return result(agentId, false, "out_of_bounds", type);
                }
                agent.controller().setSkill(new RebuildRegion(x1, y1, x2, y2));
                return result(agentId, true, "accepted", type);
            }

            case "DEFEND":{
                float x = (float)command.getDouble("x", Double.NaN);
                float y = (float)command.getDouble("y", Double.NaN);
                float radius = (float)command.getDouble("radius", Double.NaN);
                long ticks = command.getLong("ticks", -1L);
                if(!finite(x) || !finite(y) || !finite(radius) || radius < 0f || ticks < 0L){
                    return result(agentId, false, "malformed", type);
                }
                if(x < 0f || y < 0f || x >= world.width() * tilesize
                    || y >= world.height() * tilesize){
                    return result(agentId, false, "out_of_bounds", type);
                }
                agent.controller().setSkill(new DefendRegion(x, y, radius, ticks));
                return result(agentId, true, "accepted", type);
            }

            case "RETREAT":
                agent.controller().setSkill(new EmergencyRetreat());
                return result(agentId, true, "accepted", type);

            default:
                return result(agentId, false, "unknown_command", type);
        }
    }

    private static boolean finite(float v){
        return !Float.isNaN(v) && !Float.isInfinite(v);
    }

    private static boolean inBounds(int tx, int ty){
        return tx >= 0 && ty >= 0 && tx < world.width() && ty < world.height();
    }

    private static Jval result(int agentId, boolean accepted, String reason, String type){
        Jval r = Jval.newObject();
        r.put("agent_id", agentId);
        r.put("accepted", accepted);
        r.put("reason", reason);
        r.put("command_type", type);
        return r;
    }
}
