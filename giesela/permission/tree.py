from .tree_utils import Node, prepare_tree

__all__ = ["perm_tree", "perm_list"]


class perm_tree(Node):
    class admin(Node):
        class control(Node):
            execute: str
            shutdown: str
            impersonate: str

        class config(Node):
            class runtime(Node):
                edit: str
                view: str

            class guild(runtime): ...

        class permissions(Node):
            class runtime(Node):
                assign_roles: str
                edit_roles: str

            class guild(runtime): ...

        class appearance(Node):
            name: str
            avatar: str

    class queue(Node):
        class add(Node):
            entry: str
            stream: str
            playlist: str

        remove: str
        move: str
        edit: str

        class inspect(Node):
            current: str
            history: str
            queue: str

    class player(Node):
        skip: str
        revert: str
        seek: str
        pause: str
        volume: str

    class summon(Node):
        connect: str
        move: str
        steal: str

    class playlist(Node):
        class owned(Node):
            class create(Node):
                new: str
                import_pl: str

        class all(Node):
            edit: str
            remove: str
            export: str

    class webiesela(Node):
        register: str


perm_list = prepare_tree(perm_tree)
