import EntityTag from "./EntityTag";
import { Entity } from "@/lib/types";

interface Props {
  entities: Entity[];
}

export default function RelatedEntitiesPanel({ entities }: Props) {
  return (
    <div className="heritage-card p-5">
      <h2 className="section-title">Related Entities</h2>
      <div className="space-y-3">
        {entities.map((entity) => (
          <div key={entity.id} className="flex items-center justify-between">
            <EntityTag entity={entity} />
            <span className="text-xs text-gray-400">{entity.count} docs</span>
          </div>
        ))}
      </div>
    </div>
  );
}
