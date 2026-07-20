package agentcore.skill;

import java.util.List;

/** Rebuild destroyed team blocks in the engine's authoritative broken-plan order. */
public final class RebuildRegion implements Skill{
    private final int x1, y1, x2, y2;

    private BuildBlock current;
    private int initialCount = -1;
    private int completed;

    public RebuildRegion(int x1, int y1, int x2, int y2){
        this.x1 = Math.min(x1, x2);
        this.y1 = Math.min(y1, y2);
        this.x2 = Math.max(x1, x2);
        this.y2 = Math.max(y1, y2);
    }

    @Override public String type(){ return "REBUILD"; }

    public int completed(){ return completed; }
    public int initialCount(){ return Math.max(0, initialCount); }

    @Override
    public SkillResult tick(AgentBody body, long tick){
        if(current == null){
            List<RebuildSpec> broken = body.brokenBlocksInRegion(x1, y1, x2, y2);
            if(initialCount < 0) initialCount = broken.size();
            if(broken.isEmpty()){
                body.halt();
                return SkillResult.succeeded(SkillReason.REBUILT);
            }
            current = new BuildBlock(broken.get(0));
        }

        SkillResult inner = current.tick(body, tick);
        float overall = progress(inner.progress());
        if(inner.status() == agentcore.SkillStatus.SUCCEEDED){
            completed++;
            current = null;
            return SkillResult.running(SkillReason.REBUILDING, progress(0f));
        }
        return new SkillResult(inner.status(), inner.reason(), overall, inner.nextRetryTick());
    }

    private float progress(float currentProgress){
        if(initialCount <= 0) return 1f;
        return (completed + currentProgress) / initialCount;
    }
}
