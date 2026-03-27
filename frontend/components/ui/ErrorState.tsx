interface Props {
  title?: string;
  message?: string;
  onRetry?: () => void;
}

export default function ErrorState({
  title = "Something went wrong",
  message = "Unable to load content. Please try again.",
  onRetry,
}: Props) {
  return (
    <div className="heritage-card p-10 text-center text-heritage-brown">
      <p className="text-4xl mb-3">⚠️</p>
      <p className="font-serif font-semibold text-lg text-heritage-dark mb-1">{title}</p>
      <p className="text-sm mb-4">{message}</p>
      {onRetry && (
        <button onClick={onRetry} className="btn-secondary text-sm">
          Try Again
        </button>
      )}
    </div>
  );
}
