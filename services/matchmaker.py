from datetime import datetime, timezone
import networkx as nx
from typing import Dict, List, Tuple


class MatchmakerService:
    def create_pairs(
        self, user_ids: List[int], history_map: Dict[Tuple[int, int], datetime]
    ) -> Tuple[List[Tuple[int, int]], List[int]]:
        """
        Generates optimal pairs.
        :param history_map: Dict {(u1, u2): last_met_timestamp}.
        Returns: (pairs, unmatched_users)
        """
        if len(user_ids) < 2:
            return [], user_ids

        graph = nx.Graph()
        graph.add_nodes_from(user_ids)

        WEIGHT_NEVER_MET = 1_000_000_000  # ~31 years
        now = datetime.now(timezone.utc)

        for i in range(len(user_ids)):
            for j in range(i + 1, len(user_ids)):
                u1 = user_ids[i]
                u2 = user_ids[j]

                # Check if this pair has met before
                pair_key = tuple(sorted((u1, u2)))
                if pair_key in history_map:
                    last_met = history_map[pair_key]
                    delta = (now - last_met).total_seconds()
                    weight = max(1, int(delta))
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
