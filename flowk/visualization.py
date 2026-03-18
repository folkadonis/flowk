from flowk.graph import Graph

def show_graph(graph: Graph):
    """
    Prints an aesthetic flowchart representation of the graph.
    """
    print("\n" + "="*50)
    print("📊 FLOWK EXECUTION FLOW")
    print("="*50 + "\n")
    
    if not graph.entrypoint:
        print("  Empty Graph.")
        print("\n" + "="*50 + "\n")
        return
        
    visited = set()
    
    def dfs_print(node_name: str, prefix: str, is_last_sibling: bool, is_root: bool = False, branch_label: str = None):
        is_router = hasattr(graph, "routes") and node_name in graph.routes
        
        if node_name in visited:
            node_str = f"[{node_name}] 🔄 (already visited)"
        else:
            node_str = f"⟪ {node_name} ⟫ (Router)" if is_router else f"[ {node_name} ]"
            
        if is_root:
            print(f"{prefix}{node_str}")
            child_prefix = prefix
        else:
            if branch_label is not None:
                connector = "└" if is_last_sibling else "├"
                branch_str = f"{connector}─[{branch_label}]──► "
                print(f"{prefix}{branch_str}{node_str}")
                
                pad = " " if is_last_sibling else "│"
                child_prefix = prefix + pad + " " * (len(branch_str) - 1)
            else:
                print(f"{prefix}  │")
                print(f"{prefix}  ▼")
                print(f"{prefix}{node_str}")
                child_prefix = prefix

        if node_name in visited:
            return
            
        visited.add(node_name)
        
        if is_router:
            mapping = list(graph.routes[node_name].items())
            for i, (result, target) in enumerate(mapping):
                case_is_last = (i == len(mapping) - 1)
                print(f"{child_prefix}  │")
                dfs_print(target, child_prefix + "  ", case_is_last, is_root=False, branch_label=str(result))
        else:
            edges = graph.edges.get(node_name, [])
            for i, edge in enumerate(edges):
                edge_is_last = (i == len(edges) - 1)
                dfs_print(edge, child_prefix, edge_is_last, is_root=False)

    dfs_print(graph.entrypoint, "", True, is_root=True)
    print("\n" + "="*50 + "\n")
