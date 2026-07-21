package mindustry.rl;

import arc.util.io.*;
import mindustry.entities.*;
import mindustry.gen.*;
import org.junit.jupiter.api.*;

import java.util.*;

import static org.junit.jupiter.api.Assertions.*;

@SuppressWarnings("unchecked")
class EntityGroupDeterminismTest{
    @BeforeAll
    static void enableDeterministicOrder(){
        EntityGroup.enableDeterministicOrder();
    }

    @Test
    void removalPreservesInsertionOrderAndRepairsIndexes(){
        Map<Integer, Integer> indexes = new HashMap<>();
        EntityGroup<DummyEntity> group = new EntityGroup<>(
            DummyEntity.class, false, true, (entity, index) -> indexes.put(entity.id(), index));
        DummyEntity thirty = new DummyEntity(30);
        DummyEntity ten = new DummyEntity(10);
        DummyEntity twenty = new DummyEntity(20);

        indexes.put(thirty.id(), group.addIndex(thirty));
        indexes.put(ten.id(), group.addIndex(ten));
        indexes.put(twenty.id(), group.addIndex(twenty));

        assertEquals(List.of(30, 10, 20), ids(group));
        assertEquals(Map.of(30, 0, 10, 1, 20, 2), indexes);
        assertSame(twenty, group.getByID(20));

        group.removeIndex(twenty, indexes.get(20));
        indexes.remove(20);
        assertEquals(List.of(30, 10), ids(group));
        assertEquals(Map.of(30, 0, 10, 1), indexes);
    }

    @Test
    void explicitKeyCanonicalizesUnorderedAdditions(){
        EntityGroup<DummyEntity> group = new EntityGroup<>(DummyEntity.class, false, false);
        group.enableDeterministicOrder(entity -> -entity.id());

        group.add(new DummyEntity(10));
        group.add(new DummyEntity(30));
        group.add(new DummyEntity(20));

        assertEquals(List.of(30, 20, 10), ids(group));
    }

    @Test
    void orderedInsertionAheadOfUpdateCursorDoesNotRepeatCurrentEntity(){
        EntityGroup<DummyEntity> group = new EntityGroup<>(DummyEntity.class, false, false);
        List<Integer> updates = new ArrayList<>();
        DummyEntity thirty = new DummyEntity(30, () -> updates.add(30));
        DummyEntity twenty = new DummyEntity(20, () -> {
            updates.add(20);
            group.add(thirty);
        });
        DummyEntity ten = new DummyEntity(10, () -> updates.add(10));
        group.enableDeterministicOrder(entity -> -entity.id());
        group.add(twenty);
        group.add(ten);

        group.update();

        assertEquals(List.of(20, 10), updates);
        assertEquals(List.of(30, 20, 10), ids(group));
    }

    private static List<Integer> ids(EntityGroup<DummyEntity> group){
        List<Integer> result = new ArrayList<>();
        for(DummyEntity entity : group) result.add(entity.id());
        return result;
    }

    private static final class DummyEntity implements Entityc{
        private int id;
        private final Runnable updater;

        DummyEntity(int id){
            this(id, () -> {});
        }

        DummyEntity(int id, Runnable updater){
            this.id = id;
            this.updater = updater;
        }

        @Override public <T extends Entityc> T self(){ return (T)this; }
        @Override public <T> T as(){ return (T)this; }
        @Override public boolean isAdded(){ return true; }
        @Override public boolean isLocal(){ return true; }
        @Override public boolean isRemote(){ return false; }
        @Override public boolean serialize(){ return false; }
        @Override public int classId(){ return 0; }
        @Override public int id(){ return id; }
        @Override public void add(){ }
        @Override public void afterRead(){ }
        @Override public void afterReadAll(){ }
        @Override public void beforeWrite(){ }
        @Override public void id(int id){ this.id = id; }
        @Override public void read(Reads read){ }
        @Override public void remove(){ }
        @Override public void update(){ updater.run(); }
        @Override public void write(Writes write){ }
    }
}
