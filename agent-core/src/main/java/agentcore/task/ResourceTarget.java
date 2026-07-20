package agentcore.task;

import java.util.Objects;

/**
 * A quantity of a resource item (brief §10.2 "Deliver 120 copper", "Mine copper
 * until the core reaches 300").
 *
 * <p>Item types are plain strings for now (e.g. {@code "copper"}, {@code "lead"}).
 * The engine adapter maps them to real {@code mindustry.type.Item} content later;
 * this keeps the board headless and fast to test. See {@code docs/COORDINATION.md}.
 *
 * @param item   resource item type, lowercase string identifier
 * @param amount quantity in item units; non-negative
 */
public record ResourceTarget(String item, int amount) implements Target{
    public ResourceTarget{
        Objects.requireNonNull(item, "item");
        if(amount < 0){
            throw new IllegalArgumentException("resource amount must be non-negative, got " + amount);
        }
    }

    @Override public String describe(){
        return amount + " " + item;
    }
}
