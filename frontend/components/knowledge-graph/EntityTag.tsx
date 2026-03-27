import { Entity } from "@/lib/types";

const TYPE_STYLES: Record<string, string> = {
  person:       "bg-blue-100 text-blue-800 border-blue-200",
  location:     "bg-green-100 text-green-800 border-green-200",
  organization: "bg-purple-100 text-purple-800 border-purple-200",
  event:        "bg-orange-100 text-orange-800 border-orange-200",
  default:      "bg-parchment-200 text-heritage-dark border-parchment-300",
};

interface Props {
  entity: Entity;
}

export default function EntityTag({ entity }: Props) {
  const style = TYPE_STYLES[entity.type] ?? TYPE_STYLES.default;
  return (
    <span
      className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium border ${style}`}
    >
      {entity.name}
      <span className="opacity-60 capitalize">({entity.type})</span>
    </span>
  );
}
