package mindustry.entities;

import arc.*;
import arc.func.*;
import arc.math.geom.*;
import arc.struct.*;
import arc.util.*;
import arc.util.Time.*;
import arc.util.pooling.*;
import mindustry.gen.*;

import java.util.*;

import static mindustry.Vars.*;

/** Represents a group of a certain type of entity.*/
@SuppressWarnings("unchecked")
public class EntityGroup<T extends Entityc> implements Iterable<T>{
    private static int lastId = 0;
    private static boolean deterministicOrderEnabled;

    private final Seq<T> array;
    private final Seq<T> intersectArray = new Seq<>();
    private final Rect viewport = new Rect();
    private final Rect intersectRect = new Rect();
    private final EntityIndexer indexer;
    private IntMap<T> map;
    private QuadTree tree;
    private boolean clearing;
    private Intf<T> deterministicOrderKey;

    private int index;

    private double fixedCounter, timeCounter;
    private long lastTimeAccess = -1;
    private Seq<DelayRun> timeRuns = new Seq<>();

    public static int nextId(){
        if(lastId >= Integer.MAX_VALUE - 2) lastId = 0;
        return lastId++;
    }

    /** Preserve stable entity iteration for deterministic external simulation. */
    public static void enableDeterministicOrder(){
        deterministicOrderEnabled = true;
    }

    public static boolean isDeterministicOrderEnabled(){
        return deterministicOrderEnabled;
    }

    /** Canonicalize additions by an engine-owned stable key. */
    public void enableDeterministicOrder(Intf<T> key){
        deterministicOrderKey = key;
    }

    /** Makes sure the next ID counter is higher than this number, so future entities cannot possibly use this ID. */
    public static void checkNextId(int id){
        lastId = Math.max(lastId, id + 1);
    }

    public EntityGroup(Class<T> type, boolean spatial, boolean mapping){
        this(type, spatial, mapping, null);
    }

    public EntityGroup(Class<T> type, boolean spatial, boolean mapping, EntityIndexer indexer){
        array = new Seq<>(false, 32, type);

        if(spatial){
            tree = new QuadTree<>(new Rect(0, 0, 0, 0));
        }

        if(mapping){
            map = new IntMap<>();
        }

        this.indexer = indexer;
    }

    /** @return entities with colliding IDs, or an empty array. */
    public Seq<T> checkIDCollisions(){
        Seq<T> out = new Seq<>();
        IntSet ints = new IntSet();
        each(u -> {
            if(!ints.add(u.id())){
                out.add(u);
            }
        });
        return out;
    }

    public void sort(Comparator<? super T> comp){
        array.sort(comp);
    }

    public void collide(){
        collisions.collide((EntityGroup<? extends Hitboxc>)this);
    }

    public void updatePhysics(){
        collisions.updatePhysics((EntityGroup<? extends Hitboxc>)this);
    }

    public void update(){
        for(index = 0; index < array.size; index++){
            array.items[index].update();
        }
    }

    /** Calls {@link #fixedUpdate(int, int)} with a maximum of 10 updates per frame. */
    public void fixedUpdate(int targetFps){
        fixedUpdate(targetFps, 10);
    }

    /**
     * Updates this entity group at a fixed rate and delta time, regardless of framerate.
     * If updates per frame exceed {@param maxUpdatesPerFrame}, they will be skipped - visually, the game will look like it is slowing down.
     * For example, a value of 60 targetUps and 10 maxUpdatesPerFrame will mean that the game only starts slowing down below (60 / 10) = 6 FPS.
     * */
    public void fixedUpdate(int targetUps, int maxUpdatesPerFrame){
        //if fixedUpdate isn't called, e.g. when the game is paused or map is reloaded, the time counter needs to 'sync' with the actual proper time
        if(lastTimeAccess != Core.graphics.getFrameId()){
            timeCounter = Time.getInternalTime();
        }

        double targetDelta = 1.0 / targetUps;
        float timeDelta = (float)targetDelta * 60f;
        float prevDelta = Time.delta;
        double prevTime = Time.getInternalTime();
        var oldRuns = Time.getRuns();

        //since some logic (incorrectly!) relies on Time.time, it has to be passed like this across several variables.
        Time.delta = timeDelta;
        Time.setInternalTime(timeCounter);
        Time.setRuns(timeRuns);
        int updates = 0;

        fixedCounter += Core.graphics.getDeltaTime();

        while(fixedCounter >= targetDelta && updates++ < maxUpdatesPerFrame){
            //this executes any pending tasks (manually reassigned), and increments internal time, which is local to this group
            Time.update();
            update();
            fixedCounter -= targetDelta;
        }

        timeCounter = Time.getInternalTime();

        Time.delta = prevDelta;
        Time.setInternalTime(prevTime);
        Time.setRuns(oldRuns);

        lastTimeAccess = Core.graphics.getFrameId();
    }

    public Seq<T> copy(){
        return copy(new Seq<>());
    }

    public Seq<T> copy(Seq<T> arr){
        arr.addAll(array);
        return arr;
    }

    public void each(Cons<T> cons){
        for(index = 0; index < array.size; index++){
            cons.get(array.items[index]);
        }
    }

    public void each(Boolf<T> filter, Cons<T> cons){
        for(index = 0; index < array.size; index++){
            if(filter.get(array.items[index])) cons.get(array.items[index]);
        }
    }

    public void draw(Cons<T> cons){
        Core.camera.bounds(viewport);

        for(index = 0; index < array.size; index++){
            Drawc draw = (Drawc)array.items[index];
            float clip = draw.clipSize();
            if(viewport.overlaps(draw.x() - clip/2f, draw.y() - clip/2f, clip, clip)){
                cons.get((T)draw);
            }
        }
    }

    public boolean useTree(){
        return tree != null;
    }

    public boolean mappingEnabled(){
        return map != null;
    }

    @Nullable
    public T getByID(int id){
        if(map == null) throw new RuntimeException("Mapping is not enabled for group " + id + "!");
        return map.get(id);
    }

    public void removeByID(int id){
        if(map == null) throw new RuntimeException("Mapping is not enabled for group " + id + "!");
        T t = map.get(id);
        if(t != null){ //remove if present in map already
            t.remove();
        }
    }

    public void intersect(float x, float y, float width, float height, Cons<? super T> out){
        //don't waste time for empty groups
        if(isEmpty()) return;
        tree.intersect(x, y, width, height, out);
    }

    public boolean intersect(float x, float y, float width, float height, Boolf<? super T> out){
        //don't waste time for empty groups
        if(isEmpty()) return false;
        return tree.intersect(x, y, width, height, out);
    }

    public Seq<T> intersect(float x, float y, float width, float height){
        intersectArray.clear();
        //don't waste time for empty groups
        if(isEmpty()) return intersectArray;
        tree.intersect(intersectRect.set(x, y, width, height), intersectArray);
        return intersectArray;
    }

    public QuadTree tree(){
        if(tree == null) throw new RuntimeException("This group does not support quadtrees! Enable quadtrees when creating it.");
        return tree;
    }

    /** Resizes the internal quadtree, if it is enabled.*/
    public void resize(float x, float y, float w, float h){
        if(tree != null){
            tree = new QuadTree<>(new Rect(x, y, w, h));
        }
    }

    public boolean isEmpty(){
        return array.size == 0;
    }

    public T index(int i){
        return array.get(i);
    }

    public int size(){
        return array.size;
    }

    public boolean contains(Boolf<T> pred){
        return array.contains(pred);
    }

    public int count(Boolf<T> pred){
        return array.count(pred);
    }

    public void add(T type){
        if(type == null) throw new RuntimeException("Cannot add a null entity!");
        addArray(type);

        if(mappingEnabled()){
            map.put(type.id(), type);
        }
    }

    public int addIndex(T type){
        if(type == null) throw new RuntimeException("Cannot add a null entity!");
        int position = addArray(type);
        if(mappingEnabled()){
            map.put(type.id(), type);
        }
        return position;
    }

    private int addArray(T type){
        if(deterministicOrderKey != null && !array.isEmpty()){
            int typeKey = deterministicOrderKey.get(type);
            int low = 0, high = array.size;
            while(low < high){
                int middle = (low + high) >>> 1;
                T middleType = array.items[middle];
                int middleKey = deterministicOrderKey.get(middleType);
                if(middleKey < typeKey || middleKey == typeKey && middleType.id() < type.id()){
                    low = middle + 1;
                }else{
                    high = middle;
                }
            }
            int position = low;
            array.ensureCapacity(1);
            System.arraycopy(array.items, position, array.items, position + 1, array.size - position);
            array.items[position] = type;
            array.size++;
            if(indexer != null){
                for(int i = position + 1; i < array.size; i++){
                    indexer.change(array.items[i], i);
                }
            }
            if(index >= position) index++;
            return position;
        }
        int position = array.size;
        array.add(type);
        return position;
    }

    public void remove(T type){
        if(clearing) return;
        if(type == null) throw new RuntimeException("Cannot remove a null entity!");
        int idx = array.indexOf(type, true);
        if(idx != -1){
            removeArrayIndex(idx);

            if(map != null){
                map.remove(type.id());
            }

            //fix iteration index when removing
            if(index >= idx){
                index --;
            }
        }
    }

    public void removeIndex(T type, int position){
        if(clearing) return;
        if(type == null) throw new RuntimeException("Cannot remove a null entity!");
        if(position != -1 && position < array.size){

            //rarely the entity index is wrong; fallback to slow implementation
            if(array.items[position] != type){
                remove(type);
                return;
            }

            removeArrayIndex(position);

            if(map != null){
                map.remove(type.id());
            }

            //fix iteration index when removing
            if(index >= position){
                index --;
            }
        }
    }

    private void removeArrayIndex(int position){
        if(deterministicOrderEnabled){
            int moved = array.size - position - 1;
            if(moved > 0){
                System.arraycopy(array.items, position + 1, array.items, position, moved);
            }
            array.size--;
            array.items[array.size] = null;
            if(indexer != null){
                for(int i = position; i < array.size; i++){
                    indexer.change(array.items[i], i);
                }
            }
        }else{
            if(array.size > 1){
                var head = array.items[array.size - 1];
                if(indexer != null) indexer.change(head, position);
                array.items[position] = head;
            }
            array.size--;
            array.items[array.size] = null;
        }
    }

    public void clear(){
        clearing = true;

        array.each(Entityc::remove);
        array.clear();
        if(map != null) map.clear();
        Pools.freeAll(timeRuns, true);
        timeRuns.clear();

        clearing = false;
    }

    @Nullable
    public T find(Boolf<T> pred){
        return array.find(pred);
    }

    @Nullable
    public T first(){
        return array.first();
    }

    @Override
    public Iterator<T> iterator(){
        return array.iterator();
    }
}
