package agentcore.skill;

import agentcore.SkillStatus;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.*;

/**
 * State-machine tests for the M3 skills against a fake, engine-free body
 * (docs/M3_DESIGN.md D8). No content init, no JVM engine — pure FSM logic.
 */
class SkillsTest{

    /** Drive a skill to a terminal (or capped) state, advancing the body between ticks. */
    private static SkillResult run(Skill skill, FakeBody body, int maxTicks){
        SkillResult r = SkillResult.ready();
        for(int t = 0; t < maxTicks; t++){
            r = skill.tick(body, t);
            if(r.terminal()) return r;
            body.advance();
        }
        return r;
    }

    // -- NavigateTo --------------------------------------------------------

    @Test void navigateArrives(){
        FakeBody body = new FakeBody(0f, 0f);
        NavigateTo nav = new NavigateTo(100f, 0f, 4f);
        SkillResult r = run(nav, body, 500);
        assertEquals(SkillStatus.SUCCEEDED, r.status());
        assertEquals(SkillReason.ARRIVED, r.reason());
        assertTrue(body.dst(100f, 0f) <= 4f, "unit should be within tolerance");
    }

    @Test void navigateProgressMonotoneAndReported(){
        FakeBody body = new FakeBody(0f, 0f);
        NavigateTo nav = new NavigateTo(300f, 0f, 4f);
        float last = -1f;
        boolean sawRunning = false;
        for(int t = 0; t < 200; t++){
            SkillResult r = nav.tick(body, t);
            if(r.status() == SkillStatus.RUNNING){
                sawRunning = true;
                assertTrue(r.progress() >= last - 1e-4f, "progress must not regress");
                last = r.progress();
            }
            if(r.terminal()) break;
            body.advance();
        }
        assertTrue(sawRunning);
    }

    @Test void navigateBlocksWhenStuck(){
        FakeBody body = new FakeBody(0f, 0f);
        body.speed = 0f; // cannot move -> no progress
        NavigateTo nav = new NavigateTo(100f, 0f, 2f, 10, 30L);
        SkillResult r = run(nav, body, 50);
        assertEquals(SkillStatus.BLOCKED, r.status());
        assertEquals(SkillReason.STUCK, r.reason());
        assertTrue(r.nextRetryTick() >= 10, "next-retry tick should be in the future");
    }

    // -- MineResource ------------------------------------------------------

    @Test void mineReachesTargetAndCarriesExactAmount(){
        FakeBody body = new FakeBody(0f, 0f);
        body.addMineable(20, 0); // world center (164, 4)
        MineResource mine = new MineResource(20, 0, 15);
        SkillResult r = run(mine, body, 2000);
        assertEquals(SkillStatus.SUCCEEDED, r.status());
        assertEquals(SkillReason.TARGET_REACHED, r.reason());
        assertEquals(15, body.cargoAmount(), "carried cargo equals the mined target");
        assertFalse(body.isMining(), "mine tile cleared on success");
    }

    @Test void mineBlocksOnInvalidTarget(){
        FakeBody body = new FakeBody(0f, 0f);
        // no mineable tiles registered -> (5,5) is not ore
        MineResource mine = new MineResource(5, 5, 10);
        SkillResult r = mine.tick(body, 0L);
        assertEquals(SkillStatus.BLOCKED, r.status());
        assertEquals(SkillReason.INVALID_TARGET, r.reason());
    }

    @Test void mineStopsAtCapacity(){
        FakeBody body = new FakeBody(0f, 0f);
        body.capacity = 5;
        body.addMineable(10, 0);
        MineResource mine = new MineResource(10, 0, 100); // target above capacity
        SkillResult r = run(mine, body, 2000);
        assertEquals(SkillStatus.SUCCEEDED, r.status());
        assertEquals(SkillReason.CARGO_FULL, r.reason());
        assertEquals(5, body.cargoAmount());
    }

    // -- DeliverToCore -----------------------------------------------------

    @Test void deliverTransfersAllCargo(){
        FakeBody body = new FakeBody(0f, 0f);
        body.coreX = 0f; body.coreY = 0f; // already in range
        body.cargo = 18;
        DeliverToCore deliver = new DeliverToCore();
        SkillResult r = run(deliver, body, 100);
        assertEquals(SkillStatus.SUCCEEDED, r.status());
        assertEquals(SkillReason.DELIVERED, r.reason());
        assertEquals(0, body.cargoAmount());
        assertEquals(18, body.coreItems, "core gained exactly the delivered amount");
    }

    @Test void deliverNavigatesThenTransfers(){
        FakeBody body = new FakeBody(0f, 0f);
        body.coreX = 300f; body.coreY = 0f; body.coreTransferRange = 30f;
        body.cargo = 12;
        DeliverToCore deliver = new DeliverToCore();
        SkillResult r = run(deliver, body, 500);
        assertEquals(SkillStatus.SUCCEEDED, r.status());
        assertEquals(0, body.cargoAmount());
        assertEquals(12, body.coreItems);
    }

    @Test void deliverBlocksWhenCoreFull(){
        FakeBody body = new FakeBody(0f, 0f);
        body.cargo = 10;
        body.coreItems = 4000;
        body.coreCapacity = 4000; // no headroom
        DeliverToCore deliver = new DeliverToCore();
        SkillResult r = deliver.tick(body, 0L);
        assertEquals(SkillStatus.BLOCKED, r.status());
        assertEquals(SkillReason.CORE_FULL, r.reason());
    }

    @Test void deliverEmptyCargoSucceedsImmediately(){
        FakeBody body = new FakeBody(0f, 0f);
        body.cargo = 0;
        SkillResult r = new DeliverToCore().tick(body, 0L);
        assertEquals(SkillStatus.SUCCEEDED, r.status());
        assertEquals(SkillReason.DELIVERED, r.reason());
    }

    // -- Wait --------------------------------------------------------------

    @Test void waitElapsesAfterBudget(){
        FakeBody body = new FakeBody(0f, 0f);
        Wait wait = new Wait(30);
        SkillResult mid = wait.tick(body, 100L);
        assertEquals(SkillStatus.RUNNING, mid.status());
        SkillResult end = wait.tick(body, 130L);
        assertEquals(SkillStatus.SUCCEEDED, end.status());
        assertEquals(SkillReason.WAIT_ELAPSED, end.reason());
    }

    // -- SkillResult invariants -------------------------------------------

    @Test void progressClampedToUnitInterval(){
        SkillResult over = SkillResult.running(SkillReason.MOVING, 5f);
        assertEquals(1f, over.progress());
        SkillResult under = SkillResult.running(SkillReason.MOVING, -3f);
        assertEquals(0f, under.progress());
    }

    // -- full mine->deliver ledger balances --------------------------------

    @Test void mineThenDeliverBalancesLedger(){
        FakeBody body = new FakeBody(0f, 0f);
        body.coreX = 0f; body.coreY = 0f; // patch within transfer range of core
        body.addMineable(6, 0);
        int coreBefore = body.coreItems;

        SkillResult mined = run(new MineResource(6, 0, 20), body, 3000);
        assertEquals(SkillStatus.SUCCEEDED, mined.status());
        int carried = body.cargoAmount();
        assertEquals(coreBefore, body.coreItems, "mining must not leak into the core");

        SkillResult delivered = run(new DeliverToCore(), body, 200);
        assertEquals(SkillStatus.SUCCEEDED, delivered.status());
        assertEquals(carried, body.coreItems - coreBefore, "core delta equals carried amount");
        assertEquals(0, body.cargoAmount());
    }

    // -- BuildBlock -------------------------------------------------------

    @Test void buildNavigatesEnqueuesAndCompletes(){
        FakeBody body = new FakeBody(0f, 0f);
        BuildBlock build = new BuildBlock("duo", 20, 0, 1);
        SkillResult r = run(build, body, 1000);
        assertEquals(SkillStatus.SUCCEEDED, r.status());
        assertEquals(SkillReason.BUILT, r.reason());
        assertEquals(BuildTargetState.COMPLETE, body.buildState);
        assertEquals("duo", body.buildBlock);
    }

    @Test void buildBlocksOnOccupiedFootprint(){
        FakeBody body = new FakeBody(0f, 0f);
        body.buildState = BuildTargetState.OCCUPIED;
        SkillResult r = new BuildBlock("duo", 2, 2, 0).tick(body, 10L);
        assertEquals(SkillStatus.BLOCKED, r.status());
        assertEquals(SkillReason.OCCUPIED, r.reason());
        assertFalse(body.buildPlan);
    }

    @Test void buildBlocksWhenCoreResourcesStayShort(){
        FakeBody body = new FakeBody(4f, 4f);
        body.buildResources = false;
        BuildBlock build = new BuildBlock("duo", 0, 0, 0, 10, 5, 30L);
        SkillResult r = run(build, body, 20);
        assertEquals(SkillStatus.BLOCKED, r.status());
        assertEquals(SkillReason.RESOURCES_SHORT, r.reason());
        assertTrue(r.nextRetryTick() >= 30L);
    }

    @Test void buildBlocksWhenTargetCannotBeReached(){
        FakeBody body = new FakeBody(0f, 0f);
        body.speed = 0f;
        body.buildRange = 10f;
        BuildBlock build = new BuildBlock("duo", 20, 0, 0, 5, 10, 30L);
        SkillResult r = run(build, body, 20);
        assertEquals(SkillStatus.BLOCKED, r.status());
        assertEquals(SkillReason.OUT_OF_RANGE, r.reason());
    }

    @Test void buildFailsIfPlanIsRemovedExternally(){
        FakeBody body = new FakeBody(4f, 4f);
        BuildBlock build = new BuildBlock("duo", 0, 0, 0);
        assertEquals(SkillStatus.RUNNING, build.tick(body, 0L).status());
        body.buildPlan = false;
        SkillResult r = build.tick(body, 1L);
        assertEquals(SkillStatus.FAILED, r.status());
        assertEquals(SkillReason.PLAN_REMOVED, r.reason());
    }
}
