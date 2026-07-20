package agentcore.coordination;

import org.junit.jupiter.api.*;

import static org.junit.jupiter.api.Assertions.*;

class ExpertCoordinationDriverTest{
    @Test
    void recordedSnapshotsProduceDecisionSequenceParity(){
        assertDoesNotThrow(() -> DecisionParityProbe.main(new String[0]));
    }
}
