class Node:
    def __init__(self, key):
        self.key = key
        self.left = None
        self.right = None
        self.height = 1  # высота узла

    def __repr__(self):
        return f"Node({self.key})"


class AVLTree:
    def __init__(self):
        self.root = None

    # вспомогательные
    def _height(self, node):
        return node.height if node else 0

    def _update_height(self, node):
        node.height = 1 + max(self._height(node.left), self._height(node.right))

    def _balance_factor(self, node):
        return self._height(node.left) - self._height(node.right)

    # правый поворот
    def _rotate_right(self, y):
        x = y.left
        T2 = x.right

        x.right = y
        y.left = T2

        self._update_height(y)
        self._update_height(x)
        return x

    # левый поворот
    def _rotate_left(self, x):
        y = x.right
        T2 = y.left

        y.left = x
        x.right = T2

        self._update_height(x)
        self._update_height(y)
        return y

    # балансировка узла
    def _rebalance(self, node):
        self._update_height(node)
        bf = self._balance_factor(node)

        # LL
        if bf > 1 and self._balance_factor(node.left) >= 0:
            return self._rotate_right(node)
        # LR
        if bf > 1 and self._balance_factor(node.left) < 0:
            node.left = self._rotate_left(node.left)
            return self._rotate_right(node)
        # RR
        if bf < -1 and self._balance_factor(node.right) <= 0:
            return self._rotate_left(node)
        # RL
        if bf < -1 and self._balance_factor(node.right) > 0:
            node.right = self._rotate_right(node.right)
            return self._rotate_left(node)

        return node

    # поиск
    def find(self, key):
        return self._find(self.root, key)

    def _find(self, node, key):
        if node is None:
            return None
        if key == node.key:
            return node
        if key < node.key:
            return self._find(node.left, key)
        else:
            return self._find(node.right, key)

    # вставка
    def insert(self, key):
        self.root = self._insert(self.root, key)

    def _insert(self, node, key):
        if node is None:
            return Node(key)
        if key < node.key:
            node.left = self._insert(node.left, key)
        elif key > node.key:
            node.right = self._insert(node.right, key)
        else:
            # дубликаты игнорируем
            return node

        return self._rebalance(node)

    # удаление
    def delete(self, key):
        self.root, deleted = self._delete(self.root, key)
        return deleted

    def _delete(self, node, key):
        if node is None:
            return node, False

        deleted = False
        if key < node.key:
            node.left, deleted = self._delete(node.left, key)
        elif key > node.key:
            node.right, deleted = self._delete(node.right, key)
        else:
            deleted = True
            # один ребёнок или нет детей
            if node.left is None:
                return node.right, True
            elif node.right is None:
                return node.left, True
            else:
                # два ребёнка → берём минимум справа
                successor = self._min_value_node(node.right)
                node.key = successor.key
                node.right, _ = self._delete(node.right, successor.key)

        if node is None:
            return node, deleted

        # баланс после удаления
        return self._rebalance(node), deleted

    def _min_value_node(self, node):
        current = node
        while current.left:
            current = current.left
        return current

    # обходы / печать
    def inorder(self):
        res = []
        self._inorder(self.root, res)
        return res

    def _inorder(self, node, res):
        if not node:
            return
        self._inorder(node.left, res)
        res.append(node.key)
        self._inorder(node.right, res)

    def pretty_print(self):
        """Печать дерева в виде уровней."""
        lines = self._build_lines(self.root, 0, False, '-')
        for line in lines:
            print(line)

    def _build_lines(self, node, depth, is_right, sep):
        if node is None:
            return []
        key_str = f"{node.key}(h={node.height})"
        lines = [("    " * depth) + ("└── " if is_right else "┌── ") + key_str]
        left_lines = self._build_lines(node.left, depth + 1, False, sep)
        right_lines = self._build_lines(node.right, depth + 1, True, sep)
        return lines + left_lines + right_lines



avl = AVLTree()

seq = [30, 20, 10, 25, 40, 50, 5, 15, 27]
print("Исходные данные:", seq)
for v in seq:
    avl.insert(v)

print("Симметричный обход после вставки:", avl.inorder())
print("Текущее дерево:")
avl.pretty_print()

print("\nУдаляем лист (27):")
print("Удалён:", avl.delete(27))
avl.pretty_print()

avl.insert(26)
print("\nДобавили 26 (у узла 25 теперь один ребёнок). Удаляем 25:")
print("Удалён:", avl.delete(25))
avl.pretty_print()

print("\nУдаляем узел с двумя детьми (30):")
print("Удалён:", avl.delete(30))
avl.pretty_print()

print("\nИ ещё один узел с двумя детьми (20):")
print("Удалён:", avl.delete(20))
avl.pretty_print()

print("\nИтоговый симметричный обход:", avl.inorder())
