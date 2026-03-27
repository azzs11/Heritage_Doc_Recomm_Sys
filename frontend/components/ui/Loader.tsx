export default function Loader({ message = "Loading..." }: { message?: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 gap-3 text-heritage-brown">
      <div className="w-8 h-8 border-4 border-heritage-brown border-t-transparent rounded-full animate-spin" />
      <p className="text-sm font-medium">{message}</p>
    </div>
  );
}
