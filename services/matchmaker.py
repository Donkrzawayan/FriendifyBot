import networkx as nx
from typing import List, Tuple, Set


class MatchmakerService:
    def create_pairs(
        self, user_ids: List[int], past_pairs: Set[Tuple[int, int]]
    ) -> Tuple[List[Tuple[int, int]], List[int]]:
        """
        Creates pairs while avoiding duplicates.
        Returns: (pairs, unmatched_users)
        """
        if len(user_ids) < 2:
            return [], user_ids

        graph = nx.Graph()
        graph.add_nodes_from(user_ids)

        WEIGHT_NEVER_MET = 100
        WEIGHT_MET_BEFORE = 1

        for i in range(len(user_ids)):
            for j in range(i + 1, len(user_ids)):
                u1 = user_ids[i]
                u2 = user_ids[j]

                # Check if this pair has met before
                pair_key = tuple(sorted((u1, u2)))
                if pair_key in past_pairs:
                    weight = WEIGHT_MET_BEFORE
                else:
                    weight = WEIGHT_NEVER_MET

                graph.add_edge(u1, u2, weight=weight)

        matching = nx.max_weight_matching(graph, maxcardinality=True)

        pairs = []
        matched_users = set()

        for u1, u2 in matching:
            pairs.append(tuple(sorted((u1, u2))))
            matched_users.add(u1)
            matched_users.add(u2)

        unmatched = [u for u in user_ids if u not in matched_users]

        return pairs, unmatched
