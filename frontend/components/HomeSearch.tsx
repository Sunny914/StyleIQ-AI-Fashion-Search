"use client";

import { useRouter } from "next/navigation";
import { SearchForm } from "@/components/SearchForm";
import type { CategoryGender } from "@/lib/types";

export function HomeSearch() {
  const router = useRouter();

  function onSearch(query: string, gender: CategoryGender | "") {
    const params = new URLSearchParams({ q: query });
    if (gender) {
      params.set("gender", gender);
    }
    router.push(`/search?${params.toString()}`);
  }

  return <SearchForm onSearch={onSearch} />;
}
