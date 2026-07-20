package agentcore.candidates;

import java.io.ByteArrayOutputStream;
import java.util.List;

/** Immutable bounded candidate list in action-index order. */
public record CandidateSet(List<TaskCandidate> candidates){
    public CandidateSet{
        candidates = List.copyOf(candidates == null ? List.of() : candidates);
    }

    public byte[] canonicalBytes(){
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        for(TaskCandidate candidate : candidates){
            byte[] line = candidate.canonicalBytes();
            out.writeBytes(line);
            out.write('\n');
        }
        return out.toByteArray();
    }
}
