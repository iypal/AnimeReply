import { create } from "zustand";

interface UiState {
  excludeImageIds: number[];
  addExcludedId: (id: number) => void;
  clearExcludedIds: () => void;
}

export const useUiStore = create<UiState>((set) => ({
  excludeImageIds: [],
  addExcludedId: (id) =>
    set((state) => ({
      excludeImageIds: [...state.excludeImageIds, id],
    })),
  clearExcludedIds: () => set({ excludeImageIds: [] }),
}));
