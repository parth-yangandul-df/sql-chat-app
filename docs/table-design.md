You are given a task to integrate an existing React component in the codebase

The codebase should support:
- shadcn project structure  
- Tailwind CSS
- Typescript

If it doesn't, provide instructions on how to setup project via shadcn CLI, install Tailwind or Typescript.

Determine the default path for components and styles. 
If default path for components is not /components/ui, provide instructions on why it's important to create this folder
Copy-paste this component to /components/ui folder:
```tsx
spotlight-table.tsx
// components/ui/component.tsx
import { useState } from "react";

const data = [
  { id: 1, name: "Astra", role: "Engineer", status: "Active" },
  { id: 2, name: "Bravo", role: "Design", status: "Active" },
  { id: 3, name: "Charlie", role: "Marketing", status: "Offline" },
  { id: 4, name: "Delta", role: "Sales", status: "Active" },
];

export const Component = () => {
  const [q, setQ] = useState("");
  const lower = q.toLowerCase();
  return (
    <div className="h-screen grid place-content-center bg-background text-foreground p-8">
      <input
        value={q}
        onChange={(e) => setQ(e.target.value)}
        placeholder="Search name or role..."
        className="mb-4 px-4 py-2 rounded-lg border border-input bg-background max-w-sm"
      />
      <table className="min-w-[500px] border-collapse">
        <thead>
          <tr className="border-b border-border">
            <th className="p-3 text-left">Name</th>
            <th className="p-3 text-left">Role</th>
            <th className="p-3 text-left">Status</th>
          </tr>
        </thead>
        <tbody>
          {data.map((row) => {
            const hit = lower && Object.values(row).some((v) => String(v).toLowerCase().includes(lower));
            return (
              <tr
                key={row.id}
                className={`transition ${hit ? "opacity-100" : q ? "opacity-20" : "opacity-100"}`}
              >
                <td className="p-3">{row.name}</td>
                <td className="p-3">{row.role}</td>
                <td className="p-3">
                  <span
                    className={`px-2 py-1 rounded text-xs ${
                      row.status === "Active" ? "bg-green-500/20 text-green-400" : "bg-gray-500/20 text-gray-400"
                    }`}
                  >
                    {row.status}
                  </span>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
};

demo.tsx
import { Component } from "@/components/ui/spotlight-table";

export default function DemoOne() {
  return <Component />;
}

```

Implementation Guidelines
 1. Analyze the component structure and identify all required dependencies
 2. Review the component's argumens and state
 3. Identify any required context providers or hooks and install them
 4. Questions to Ask
 - What data/props will be passed to this component?
 - Are there any specific state management requirements?
 - Are there any required assets (images, icons, etc.)?
 - What is the expected responsive behavior?
 - What is the best place to use this component in the app?

Steps to integrate
 0. Copy paste all the code above in the correct directories
 1. Install external dependencies
 2. Fill image assets with Unsplash stock images you know exist
 3. Use lucide-react icons for svgs or logos if component requires them
