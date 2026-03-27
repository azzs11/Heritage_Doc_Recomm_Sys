import Loader from "@/components/ui/Loader";

export default function Loading() {
  return (
    <div className="min-h-[60vh] flex items-center justify-center">
      <Loader message="Loading..." />
    </div>
  );
}
