"use client";

import { useRouter } from "next/navigation";
import { PageShell } from "@/components/common/PageShell";
import { DroneCard } from "@/components/common/DroneCard";
import { EmptyState } from "@/components/common/EmptyState";
import { useDroneStore } from "@/stores/droneStore";
import { Plane } from "lucide-react";

export default function FleetPage() {
  const drones = useDroneStore((s) => s.drones);
  const selectedDroneId = useDroneStore((s) => s.selectedDroneId);
  const selectDrone = useDroneStore((s) => s.selectDrone);
  const router = useRouter();

  function handleDroneClick(droneId: number) {
    selectDrone(droneId);
    router.push(`/fleet/${droneId}`);
  }

  return (
    <PageShell
      title="Fleet Overview"
      description={`${drones.length} drones in fleet`}
    >
      {drones.length === 0 ? (
        <EmptyState
          title="No drones connected"
          description="Waiting for Digital Twin to provide drone state data."
          icon={<Plane className="h-10 w-10" />}
        />
      ) : (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {drones.map((drone) => (
            <DroneCard
              key={drone.drone_id}
              drone={drone}
              selected={selectedDroneId === drone.drone_id}
              onClick={() => handleDroneClick(drone.drone_id)}
            />
          ))}
        </div>
      )}
    </PageShell>
  );
}
