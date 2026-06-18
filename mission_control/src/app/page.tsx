export default function Home() {
  return (
    <div className="min-h-screen bg-neutral-950 text-neutral-50 font-sans">
      {/* Header */}
      <header className="border-b border-neutral-800 bg-neutral-900 px-6 py-4 flex items-center justify-between">
        <h1 className="text-xl font-bold tracking-tight text-white flex items-center gap-2">
          <span className="text-blue-500">◆</span> Agora Mission Control v4.0
        </h1>
        <div className="flex items-center gap-4 text-sm">
          <span className="bg-green-500/10 text-green-400 px-2 py-1 rounded-full border border-green-500/20">
            System Online
          </span>
        </div>
      </header>

      {/* Main Content */}
      <main className="p-6 max-w-7xl mx-auto space-y-6">
        
        {/* Top Stats */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div className="bg-neutral-900 border border-neutral-800 p-4 rounded-xl">
            <h3 className="text-neutral-400 text-sm font-medium">Active Agents</h3>
            <p className="text-3xl font-light text-white mt-1">8</p>
          </div>
          <div className="bg-neutral-900 border border-neutral-800 p-4 rounded-xl">
            <h3 className="text-neutral-400 text-sm font-medium">Running Experiments</h3>
            <p className="text-3xl font-light text-white mt-1">2</p>
          </div>
          <div className="bg-neutral-900 border border-neutral-800 p-4 rounded-xl">
            <h3 className="text-neutral-400 text-sm font-medium">GPU Utilization (H100)</h3>
            <p className="text-3xl font-light text-white mt-1">84%</p>
          </div>
          <div className="bg-neutral-900 border border-neutral-800 p-4 rounded-xl">
            <h3 className="text-neutral-400 text-sm font-medium">Est. Monthly Cost</h3>
            <p className="text-3xl font-light text-white mt-1">$45.50</p>
          </div>
        </div>

        {/* Agent Fleet */}
        <div className="bg-neutral-900 border border-neutral-800 rounded-xl overflow-hidden">
          <div className="px-4 py-3 border-b border-neutral-800 bg-neutral-900">
            <h2 className="text-lg font-medium text-white">Agent Fleet Status</h2>
          </div>
          <div className="divide-y divide-neutral-800">
            {['Socrates', 'Galois', 'Euler', 'Pythagore', 'Turing'].map(agent => (
              <div key={agent} className="p-4 flex items-center justify-between hover:bg-neutral-800/50 transition-colors">
                <div className="flex items-center gap-3">
                  <div className="w-2 h-2 rounded-full bg-green-500"></div>
                  <span className="font-medium text-white">{agent} Agent</span>
                </div>
                <div className="text-sm text-neutral-400">
                  {agent === 'Socrates' ? 'Orchestrating Elenchus' : 'Awaiting A2A Task'}
                </div>
              </div>
            ))}
          </div>
        </div>

      </main>
    </div>
  );
}
