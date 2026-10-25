import Link from "next/link";
import { ProductDetailView } from "@/components/ProductDetailView";

type ProductPageProps = {
  params: Promise<{ id: string }>;
};

export default async function ProductPage({ params }: ProductPageProps) {
  const { id } = await params;
  return (
    <section className="page">
      <p className="eyebrow">
        <Link href="/search">Search</Link>
      </p>
      <ProductDetailView productId={decodeURIComponent(id)} />
    </section>
  );
}
