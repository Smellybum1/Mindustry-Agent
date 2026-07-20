package agentcore.task;

import java.util.Collections;
import java.util.Map;
import java.util.Objects;
import java.util.SortedMap;
import java.util.TreeMap;

/**
 * An immutable, deterministically-ordered estimate of the resources a task will
 * consume (brief §11.3 {@code estimated_resource_cost}, e.g. {@code {"copper": 120}}).
 *
 * <p>Backed by a {@link TreeMap} so iteration order is stable (item name ascending),
 * which matters for deterministic hashing, event serialization, and announcement
 * rendering. Item types are strings; see {@link ResourceTarget} for the rationale.
 */
public final class ResourceCost{
    private static final ResourceCost EMPTY = new ResourceCost(new TreeMap<>());

    private final SortedMap<String, Integer> amounts;

    private ResourceCost(SortedMap<String, Integer> amounts){
        this.amounts = Collections.unmodifiableSortedMap(amounts);
    }

    /** The empty cost. */
    public static ResourceCost empty(){
        return EMPTY;
    }

    /** A cost of a single item type. */
    public static ResourceCost of(String item, int amount){
        Objects.requireNonNull(item, "item");
        requireNonNegative(amount);
        SortedMap<String, Integer> m = new TreeMap<>();
        if(amount != 0) m.put(item, amount);
        return new ResourceCost(m);
    }

    /** A cost copied from an arbitrary map; zero entries are dropped, order canonicalized. */
    public static ResourceCost of(Map<String, Integer> costs){
        Objects.requireNonNull(costs, "costs");
        SortedMap<String, Integer> m = new TreeMap<>();
        for(Map.Entry<String, Integer> e : costs.entrySet()){
            Objects.requireNonNull(e.getKey(), "item");
            int amount = Objects.requireNonNull(e.getValue(), "amount");
            requireNonNegative(amount);
            if(amount != 0) m.put(e.getKey(), amount);
        }
        return m.isEmpty() ? EMPTY : new ResourceCost(m);
    }

    /** Estimated amount of {@code item}; 0 if not present. */
    public int amount(String item){
        return amounts.getOrDefault(item, 0);
    }

    /** True if no resources are estimated. */
    public boolean isEmpty(){
        return amounts.isEmpty();
    }

    /** The backing amounts as an unmodifiable, ascending-by-item map. */
    public SortedMap<String, Integer> asMap(){
        return amounts;
    }

    private static void requireNonNegative(int amount){
        if(amount < 0) throw new IllegalArgumentException("resource amount must be non-negative, got " + amount);
    }

    @Override public boolean equals(Object o){
        if(this == o) return true;
        if(!(o instanceof ResourceCost other)) return false;
        return amounts.equals(other.amounts);
    }

    @Override public int hashCode(){
        return amounts.hashCode();
    }

    @Override public String toString(){
        return amounts.toString();
    }
}
