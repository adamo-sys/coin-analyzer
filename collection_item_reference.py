"""Runtime authority for deferred item actions; never serialize these references."""
from dataclasses import dataclass

from coin_collection import CoinCollection, CoinItem, CollectionLoadState


@dataclass(frozen=True, eq=False)
class CollectionItemReference:
    collection: CoinCollection
    item: CoinItem
    item_id: str

    @classmethod
    def capture(cls, collection: CoinCollection, item: CoinItem):
        reference = cls(collection, item, item.id)
        reference.resolve(collection)
        return reference

    def resolve(self, collection: CoinCollection) -> CoinItem:
        if collection is not self.collection or collection.load_state is not CollectionLoadState.LOADED:
            raise ValueError("The active collection changed or is unavailable; refresh the action.")
        matches = [item for item in collection.items if item.id == self.item_id]
        if not self.item_id.strip() or len(matches) != 1 or matches[0] is not self.item:
            raise ValueError("The referenced item changed or is unavailable; refresh the action.")
        return self.item
