package agentcore.skill;

import agentcore.SkillStatus;

import java.util.*;

/** Execute an authoritative ordered schematic as sequential {@link BuildBlock}s. */
public final class ExecuteSchematic implements Skill{
    private final String name;
    private final int anchorX, anchorY;
    private final List<BuildSpec> blocks;

    private int completed;
    private BuildBlock current;

    public ExecuteSchematic(String name, int anchorX, int anchorY, List<BuildSpec> blocks){
        if(name == null || name.isBlank()) throw new IllegalArgumentException("name is blank");
        if(blocks == null || blocks.isEmpty()) throw new IllegalArgumentException("blocks is empty");
        this.name = name;
        this.anchorX = anchorX;
        this.anchorY = anchorY;
        this.blocks = List.copyOf(blocks);
    }

    @Override public String type(){ return "SCHEMATIC"; }

    public String name(){ return name; }
    public int completed(){ return completed; }
    public int total(){ return blocks.size(); }

    @Override
    public SkillResult tick(AgentBody body, long tick){
        if(completed >= blocks.size()) return SkillResult.succeeded(SkillReason.BUILT);
        if(current == null){
            BuildSpec spec = blocks.get(completed);
            current = new BuildBlock(spec.block(), anchorX + spec.offsetX(),
                anchorY + spec.offsetY(), spec.rotation());
        }

        SkillResult inner = current.tick(body, tick);
        float overall = (completed + inner.progress()) / blocks.size();
        if(inner.status() == SkillStatus.SUCCEEDED){
            completed++;
            current = null;
            if(completed == blocks.size()) return SkillResult.succeeded(SkillReason.BUILT);
            return SkillResult.running(SkillReason.BUILDING, completed / (float)blocks.size());
        }
        return new SkillResult(inner.status(), inner.reason(), overall, inner.nextRetryTick());
    }
}
