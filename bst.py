from __future__ import annotations
from typing import Optional, Any, List


class Node:
    def __init__(self, key: Any, parent: Optional[Node] = None):
        self.key = key
        self.left: Optional[Node] = None
        self.right: Optional[Node] = None
        self.parent: Optional[Node] = parent

    def __repr__(self):
        return f"Node({self.key})"


class BinarySearchTree:
    def __init__(self):
        self.root: Optional[Node] = None

    def search(self, key: Any) -> Optional[Node]:
        cur = self.root
        while cur is not None:
            if key == cur.key:
                return cur
            if key < cur.key:
                cur = cur.left
            else:
                cur = cur.right
        return None

    def minimum(self, start: Optional[Node] = None) -> Optional[Node]:
        cur = start if start is not None else self.root
        if cur is None:
            return None
        while cur.left is not None:
            cur = cur.left
        return cur

    def maximum(self, start: Optional[Node] = None) -> Optional[Node]:
        cur = start if start is not None else self.root
        if cur is None:
            return None
        while cur.right is not None:
            cur = cur.right
        return cur

    def insert(self, key: Any) -> Node:
        parent: Optional[Node] = None
        cur = self.root
        while cur is not None:
            parent = cur
            if key < cur.key:
                cur = cur.left
            else:
                cur = cur.right
        node = Node(key, parent)
        if parent is None:
            self.root = node
        elif key < parent.key:
            parent.left = node
        else:
            parent.right = node
        return node

    def successor(self, node: Node) -> Optional[Node]:
        if node.right is not None:
            return self.minimum(node.right)
        cur = node
        parent = cur.parent
        while parent is not None and cur is parent.right:
            cur = parent
            parent = parent.parent
        return parent

    def _transplant(self, u: Node, v: Optional[Node]) -> None:
        if u.parent is None:
            self.root = v
        elif u is u.parent.left:
            u.parent.left = v
        else:
            u.parent.right = v
        if v is not None:
            v.parent = u.parent

    def delete(self, key: Any) -> bool:
        node = self.search(key)
        if node is None:
            return False
        if node.left is None:
            self._transplant(node, node.right)
        elif node.right is None:
            self._transplant(node, node.left)
        else:
            succ = self.minimum(node.right)
            assert succ is not None
            if succ.parent is not node:
                self._transplant(succ, succ.right)
                succ.right = node.right
                if succ.right:
                    succ.right.parent = succ
            self._transplant(node, succ)
            succ.left = node.left
            if succ.left:
                succ.left.parent = succ
        return True

    def inorder_keys(self) -> List[Any]:
        res: List[Any] = []
        def _inorder(n: Optional[Node]):
            if n is None:
                return
            _inorder(n.left)
            res.append(n.key)
            _inorder(n.right)
        _inorder(self.root)
        return res


bst = BinarySearchTree()
for k in [50, 30, 70, 20, 40, 60, 80]:
    bst.insert(k)

# Вариант 1: добавления
additions = [27, 34, 17, 20, 10, 5, 15, 11, 14, 12, 16, 40, 33, 37]
for a in additions:
    bst.insert(a)


# Удаления
deletions = [33, 15, 14]
for d in deletions:
    ok = bst.delete(d)
    print(f"Delete {d}:", ok)

print("In-order after deletions:", bst.inorder_keys())
