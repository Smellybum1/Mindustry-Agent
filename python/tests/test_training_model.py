import importlib.util
import unittest


@unittest.skipIf(importlib.util.find_spec("torch") is None, "RL extra is not installed")
class TestSelectorModel(unittest.TestCase):
    def test_pinned_shapes_masks_and_seeded_initialization(self):
        import torch

        from mindustry_agents.training.model import SelectorActorCritic

        first = SelectorActorCritic(123)
        second = SelectorActorCritic(123)
        candidates = torch.zeros((2, 8, 37))
        scalars = torch.zeros((2, 56))
        present = torch.tensor([[True] * 3 + [False] * 5] * 2)
        mask = torch.tensor([[True, False, True] + [False] * 6 + [True]] * 2)
        raw, masked, value = first(candidates, scalars, present, mask)
        self.assertEqual(tuple(raw.shape), (2, 10))
        self.assertEqual(tuple(value.shape), (2,))
        self.assertTrue(torch.isneginf(masked[:, 1]).all() or (masked[:, 1] < -1e30).all())
        self.assertTrue(
            all(torch.equal(left, right) for left, right in zip(first.state_dict().values(), second.state_dict().values()))
        )


if __name__ == "__main__":
    unittest.main()
