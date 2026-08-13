import { FolderKanban, Plus, Clock, MoreVertical, FileText } from "lucide-react";

export default function ProjectPage() {
  const projects = [
    { id: 1, name: "Website Redesign", status: "In Progress", date: "Aug 12, 2026", color: "from-blue-500 to-cyan-500" },
    { id: 2, name: "API Integration", status: "Planning", date: "Aug 10, 2026", color: "from-purple-500 to-pink-500" },
    { id: 3, name: "Sarla AI Memory", status: "Completed", date: "Aug 05, 2026", color: "from-emerald-500 to-teal-500" },
  ];

  return (
    <div className="flex-1 overflow-y-auto p-4 md:p-8 animate-fade-in custom-scrollbar">
      {/* Header */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center mb-10 gap-4">
        <div>
          <h1 className="text-3xl font-bold text-white mb-2 flex items-center gap-3">
            <FolderKanban className="text-indigo-400" size={32} />
            My Projects
          </h1>
          <p className="text-slate-400">Manage and organize your AI-assisted projects.</p>
        </div>
        
        <button className="flex items-center gap-2 bg-indigo-600 hover:bg-indigo-500 text-white px-6 py-3 rounded-xl font-medium transition-all shadow-[0_0_15px_rgba(79,70,229,0.4)]">
          <Plus size={20} />
          New Project
        </button>
      </div>

      {/* Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {projects.map((project) => (
          <div key={project.id} className="glass rounded-2xl p-6 hover:bg-white/5 transition-all group cursor-pointer border border-white/5 hover:border-indigo-500/30">
            <div className="flex justify-between items-start mb-4">
              <div className={`w-12 h-12 rounded-xl bg-gradient-to-br ${project.color} flex items-center justify-center shadow-lg group-hover:scale-110 transition-transform`}>
                <FileText className="text-white" size={24} />
              </div>
              <button className="text-slate-500 hover:text-white transition-colors">
                <MoreVertical size={20} />
              </button>
            </div>
            
            <h3 className="text-xl font-semibold text-white mb-2 group-hover:text-indigo-300 transition-colors">
              {project.name}
            </h3>
            
            <div className="flex items-center justify-between mt-6 pt-4 border-t border-white/10">
              <span className={`text-xs px-3 py-1 rounded-full ${
                project.status === 'Completed' ? 'bg-emerald-500/20 text-emerald-400' :
                project.status === 'In Progress' ? 'bg-blue-500/20 text-blue-400' :
                'bg-slate-500/20 text-slate-400'
              }`}>
                {project.status}
              </span>
              <span className="flex items-center gap-1 text-xs text-slate-500">
                <Clock size={14} />
                {project.date}
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
