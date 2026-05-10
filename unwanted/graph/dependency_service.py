import networkx as nx


class DependencyService:
    def build_graph_response(self, dependencies, metrics):
        G = nx.DiGraph()

        for dep in dependencies:
            G.add_edge(
                dep["source"],
                dep["target"],
                relation=dep["type"]
            )

        nodes = []
        edges = []

        for node in G.nodes():
            metric = metrics.get(node, {})
            complexity = metric.get("avg_complexity", 0)

            nodes.append({
                "id": node,
                "label": node,
                "complexity": complexity,
                "maintainability": 100 - complexity,
                "loc": metric.get("code_lines", 0)
            })

        for src, dst, attrs in G.edges(data=True):
            edges.append({
                "source": src,
                "target": dst,
                "type": attrs.get("relation", "dependency")
            })

        return {
            "nodes": nodes,
            "edges": edges
        }