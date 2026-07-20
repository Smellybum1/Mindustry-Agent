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

    @Test void schematicExecutesAuthoritativeOrderAndReportsProgress(){
        FakeBody body = new FakeBody(4f, 4f);
        ExecuteSchematic schematic = new ExecuteSchematic("two_blocks", 10, 10, java.util.List.of(
            new BuildSpec("duo", 0, -1, 1),
            new BuildSpec("copper-wall", 1, 0, 0)
        ));
        float last = 0f;
        SkillResult result = SkillResult.ready();
        for(int tick = 0; tick < 500; tick++){
            result = schematic.tick(body, tick);
            assertTrue(result.progress() >= last - 1e-5f, "schematic progress regressed");
            last = result.progress();
            if(result.terminal()) break;
            body.advance();
        }
        assertEquals(SkillStatus.SUCCEEDED, result.status());
        assertEquals(2, schematic.completed());
        assertEquals(2, schematic.total());
        assertEquals("copper-wall", body.buildBlock, "second authoritative entry ran last");
    }

    @Test void supplyWithdrawsAndDepositsExactRequestedAmount(){
        FakeBody body = new FakeBody(4f, 4f);
        body.coreItems = 30;
        SupplyBuilding supply = new SupplyBuilding("copper", 8, 8, 30);
        SkillResult result = run(supply, body, 20);
        assertEquals(SkillStatus.SUCCEEDED, result.status());
        assertEquals(SkillReason.SUPPLIED, result.reason());
        assertEquals(30, supply.delivered());
        assertEquals(0, body.coreItems);
        assertEquals(0, body.cargo);
        assertEquals(60, body.supplyStock);
        assertEquals(0, supply.targetStockBefore());
        assertEquals(60, supply.targetStock());
    }

    @Test void supplyStopsAtTargetCapacityAndReportsActualDelivery(){
        FakeBody body = new FakeBody(4f, 4f);
        body.coreItems = 30;
        body.supplyCapacity = 15;
        SupplyBuilding supply = new SupplyBuilding("copper", 8, 8, 30);
        SkillResult result = run(supply, body, 20);
        assertEquals(SkillStatus.SUCCEEDED, result.status());
        assertEquals(0.5f, result.progress(), 1e-6f);
        assertEquals(15, supply.delivered());
        assertEquals(15, body.coreItems);
        assertEquals(0, body.cargo);
        assertEquals(30, body.supplyStock);
        assertEquals(0, supply.targetStockBefore());
        assertEquals(30, supply.targetStock());
    }

    @Test void supplyBlocksWhenCoreRunsShortAfterPartialDelivery(){
        FakeBody body = new FakeBody(4f, 4f);
        body.coreItems = 10;
        SupplyBuilding supply = new SupplyBuilding("copper", 8, 8, 30);
        SkillResult result = run(supply, body, 20);
        assertEquals(SkillStatus.BLOCKED, result.status());
        assertEquals(SkillReason.CORE_SHORT, result.reason());
        assertEquals(10, supply.delivered());
        assertEquals(0, body.coreItems);
        assertEquals(0, body.cargo);
        assertEquals(0, supply.targetStockBefore());
        assertEquals(20, supply.targetStock());
    }

    @Test void supplyRejectsMismatchedExistingCargo(){
        FakeBody body = new FakeBody(4f, 4f);
        body.coreItems = 30;
        body.cargo = 5;
        body.cargoItem = "lead";
        SkillResult result = new SupplyBuilding("copper", 8, 8, 10).tick(body, 0);
        assertEquals(SkillStatus.BLOCKED, result.status());
        assertEquals(SkillReason.CARGO_MISMATCH, result.reason());
        assertEquals(5, body.cargo);
        assertEquals(30, body.coreItems);
    }

    @Test void supplyFullTargetSucceedsWithoutWithdrawing(){
        FakeBody body = new FakeBody(4f, 4f);
        body.coreItems = 30;
        body.supplyCapacity = 0;
        SupplyBuilding supply = new SupplyBuilding("copper", 8, 8, 30);
        SkillResult result = supply.tick(body, 0);
        assertEquals(SkillStatus.SUCCEEDED, result.status());
        assertEquals(SkillReason.SUPPLIED, result.reason());
        assertEquals(0f, result.progress(), 1e-6f);
        assertEquals(0, supply.delivered());
        assertEquals(30, body.coreItems);
        assertEquals(0, body.cargo);
    }

    @Test void rebuildRegionRestoresQueuedBrokenBlock(){
        FakeBody body = new FakeBody(4f, 4f);
        body.broken.add(new RebuildSpec("copper-wall", 8, 8, 0));
        RebuildRegion rebuild = new RebuildRegion(7, 7, 9, 9);
        SkillResult result = run(rebuild, body, 200);
        assertEquals(SkillStatus.SUCCEEDED, result.status());
        assertEquals(SkillReason.REBUILT, result.reason());
        assertEquals(1, rebuild.initialCount());
        assertEquals(1, rebuild.completed());
        assertTrue(body.broken.isEmpty());
        assertEquals(BuildTargetState.COMPLETE, body.buildState);
    }

    @Test void rebuildRegionIgnoresPlansOutsideRect(){
        FakeBody body = new FakeBody(4f, 4f);
        body.broken.add(new RebuildSpec("copper-wall", 20, 20, 0));
        RebuildRegion rebuild = new RebuildRegion(7, 7, 9, 9);
        SkillResult result = rebuild.tick(body, 0);
        assertEquals(SkillStatus.SUCCEEDED, result.status());
        assertEquals(0, rebuild.initialCount());
        assertEquals(1, body.broken.size());
        assertFalse(body.buildPlan);
    }

    @Test void rebuildRegionPropagatesResourceShortage(){
        FakeBody body = new FakeBody(4f, 4f);
        body.broken.add(new RebuildSpec("copper-wall", 8, 8, 0));
        body.buildResources = false;
        RebuildRegion rebuild = new RebuildRegion(7, 7, 9, 9);
        SkillResult result = run(rebuild, body, 200);
        assertEquals(SkillStatus.BLOCKED, result.status());
        assertEquals(SkillReason.RESOURCES_SHORT, result.reason());
        assertEquals(0, rebuild.completed());
        assertEquals(1, body.broken.size());
    }

    @Test void defendBreaksEqualDistanceTieByLowestUnitId(){
        FakeBody body = new FakeBody(0f, 0f);
        body.enemies.add(new FakeBody.FakeEnemy(9, 10f, 0f));
        body.enemies.add(new FakeBody.FakeEnemy(3, -10f, 0f));
        DefendRegion defend = new DefendRegion(0f, 0f, 20f, 10L);
        SkillResult result = defend.tick(body, 0L);
        assertEquals(SkillStatus.RUNNING, result.status());
        assertEquals(SkillReason.DEFENDING, result.reason());
        assertEquals(3, defend.targetId());
        assertEquals(3, body.targetId);
        assertTrue(body.firing);
    }

    @Test void defendWaitsForRegionToClearAfterDuration(){
        FakeBody body = new FakeBody(0f, 0f);
        body.enemies.add(new FakeBody.FakeEnemy(4, 10f, 0f));
        DefendRegion defend = new DefendRegion(0f, 0f, 20f, 5L);
        assertEquals(SkillStatus.RUNNING, defend.tick(body, 5L).status());
        assertEquals(SkillStatus.RUNNING, defend.tick(body, 10L).status());
        body.enemies.clear();
        SkillResult result = defend.tick(body, 11L);
        assertEquals(SkillStatus.SUCCEEDED, result.status());
        assertEquals(SkillReason.DEFENDED, result.reason());
        assertFalse(body.firing);
        body.enemies.add(new FakeBody.FakeEnemy(1, 1f, 0f));
        assertEquals(SkillStatus.SUCCEEDED, defend.tick(body, 12L).status());
        assertFalse(body.firing, "a terminal defense must not reacquire later targets");
    }

    @Test void retreatCancelsBuildReturnsCoreAndPreservesCargo(){
        FakeBody body = new FakeBody(100f, 0f);
        body.coreX = 0f;
        body.coreY = 0f;
        body.cargo = 17;
        body.buildPlan = true;
        body.firing = true;
        SkillResult result = run(new EmergencyRetreat(), body, 100);
        assertEquals(SkillStatus.SUCCEEDED, result.status());
        assertEquals(SkillReason.RETREATED, result.reason());
        assertTrue(body.buildPlansCancelled);
        assertFalse(body.buildPlan);
        assertFalse(body.firing);
        assertEquals(17, body.cargo);
        assertTrue(body.dst(body.coreX, body.coreY) <= 8f);
    }

    @Test void retreatBlocksWithoutCoreAfterCancellingPlans(){
        FakeBody body = new FakeBody(100f, 0f);
        body.hasCore = false;
        body.buildPlan = true;
        SkillResult result = new EmergencyRetreat().tick(body, 7L);
        assertEquals(SkillStatus.BLOCKED, result.status());
        assertEquals(SkillReason.NO_CORE, result.reason());
        assertEquals(67L, result.nextRetryTick());
        assertTrue(body.buildPlansCancelled);
    }
}
