"use client"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Brain, Link, Folder, Send } from "lucide-react"
import { LiquidMetal, PulsingBorder } from "@paper-design/shaders-react"
import { motion } from "framer-motion"
import { useState, useRef, useEffect } from "react"
import { Toaster, toast } from "sonner"

interface Message {
  id: string
  content: string
  role: "user" | "assistant"
}

export function ChatInterface() {
  const [isFocused, setIsFocused] = useState(false)
  const [messages, setMessages] = useState<Message[]>([])
  const [inputValue, setInputValue] = useState("")
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [sessionId, setSessionId] = useState<string | null>(null)
  const chatContainerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (chatContainerRef.current) {
      chatContainerRef.current.scrollTop = chatContainerRef.current.scrollHeight
    }
  }, [messages])

  useEffect(() => {
    // Generate a unique session ID on component mount
    const newSessionId = `sess_${Date.now()}_${Math.random().toString(36).substring(2, 9)}`;
    setSessionId(newSessionId);
  }, []);


  const handleSendMessage = async () => {
    if (!inputValue.trim()) return

    const userMessage: Message = {
      id: Date.now().toString(),
      content: inputValue,
      role: "user",
    }
    setMessages((prev) => [...prev, userMessage])
    setInputValue("")
    setIsLoading(true)
    setError(null)

    try {
      const response = await fetch("/api/chat", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ question: inputValue, session_id: sessionId }),
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || "Failed to get response from server")
      }

      const result = await response.json()

      // UPDATE sessionId from backend response
      if (result.session_id) {
        setSessionId(result.session_id);
      }

      const assistantMessage: Message = {
        id: (Date.now() + 1).toString(),
        content: result.answer,
        role: "assistant",
      }
      setMessages((prev) => [...prev, assistantMessage])
    } catch (err: any) {
      setError(err.message)
      toast.error(err.message)
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="flex flex-col items-center justify-center min-h-screen p-4 bg-black text-white">
      <Toaster position="top-center" richColors />
      <div className="w-full max-w-4xl flex flex-col h-[90vh]">
        {/* Chat Messages Display */}
        <div ref={chatContainerRef} className="flex-1 overflow-y-auto p-4 space-y-4">
          {messages.map((msg) => (
            <div key={msg.id} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
              <div className={`max-w-lg px-4 py-2 rounded-lg ${msg.role === 'user' ? 'bg-orange-600' : 'bg-zinc-800'}`}>
                <p className="text-sm">{msg.content}</p>
              </div>
            </div>
          ))}
          {isLoading && messages.length > 0 && messages[messages.length - 1].role === 'user' && (
            <div className="flex justify-start">
              <div className="max-w-lg px-4 py-2 rounded-lg bg-zinc-800">
                <p className="text-sm">Thinking...</p>
              </div>
            </div>
          )}
        </div>

        {/* Input Area */}
        <div className="relative mt-4">
          <div className="flex flex-row items-center mb-2 justify-center">
            {messages.length === 0 && (
              <>
                {/* Shader Circle */}
                <motion.div
                  id="circle-ball"
                  className="relative flex items-center justify-center z-10"
                  animate={{
                    y: isFocused ? 50 : 0,
                    opacity: isFocused ? 0 : 1,
                    filter: isFocused ? "blur(4px)" : "blur(0px)",
                    rotate: isFocused ? 180 : 0,
                  }}
                  transition={{ duration: 0.5, type: "spring", stiffness: 200, damping: 20 }}
                >
                  <div className="z-10 absolute bg-white/5 h-11 w-11 rounded-full backdrop-blur-[3px]">
                    <div className="h-[2px] w-[2px] bg-white rounded-full absolute top-4 left-4 blur-[1px]" />
                    <div className="h-[2px] w-[2px] bg-white rounded-full absolute top-3 left-7 blur-[0.8px]" />
                    <div className="h-[2px] w-[2px] bg-white rounded-full absolute top-8 left-2 blur-[1px]" />
                    <div className="h-[2px] w-[2px] bg-white rounded-full absolute top-5 left-9 blur-[0.8px]" />
                    <div className="h-[2px] w-[2px] bg-white rounded-full absolute top-7 left-7 blur-[1px]" />
                  </div>
                  <LiquidMetal style={{ height: 80, width: 80, filter: "blur(14px)", position: "absolute" }} colorBack="hsl(0, 0%, 0%, 0)" colorTint="hsl(29, 77%, 49%)" repetition={4} softness={0.5} shiftRed={0.3} shiftBlue={0.3} distortion={0.1} contour={1} shape="circle" offsetX={0} offsetY={0} scale={0.58} rotation={50} speed={5} />
                  <LiquidMetal style={{ height: 80, width: 80 }} colorBack="hsl(0, 0%, 0%, 0)" colorTint="hsl(29, 77%, 49%)" repetition={4} softness={0.5} shiftRed={0.3} shiftBlue={0.3} distortion={0.1} contour={1} shape="circle" offsetX={0} offsetY={0} scale={0.58} rotation={50} speed={5} />
                </motion.div>

                {/* Greeting Text */}
                <motion.p
                  className="text-white/40 text-sm font-light z-10"
                  animate={{
                    y: isFocused ? 50 : 0,
                    opacity: isFocused ? 0 : 1,
                    filter: isFocused ? "blur(4px)" : "blur(0px)",
                  }}
                  transition={{ duration: 0.5, type: "spring", stiffness: 200, damping: 20 }}
                >
                  Hey there! I'm here to help with anything you need
                </motion.p>
              </>
            )}
          </div>

          <div className="relative">
            <motion.div
              className="absolute w-full h-full z-0 flex items-center justify-center"
              initial={{ opacity: 0 }}
              animate={{ opacity: isFocused ? 1 : 0 }}
              transition={{ duration: 0.8 }}
            >
              <PulsingBorder style={{ height: "146.5%", minWidth: "143%" }} colorBack="hsl(0, 0%, 0%)" roundness={0.18} thickness={0} softness={0} intensity={0.3} bloom={2} spots={2} spotSize={0.25} pulse={0} smoke={0.35} smokeSize={0.4} scale={0.7} rotation={0} offsetX={0} offsetY={0} speed={1} colors={["hsl(29, 70%, 37%)", "hsl(32, 100%, 83%)", "hsl(4, 32%, 30%)", "hsl(25, 60%, 50%)", "hsl(0, 100%, 10%)"]} />
            </motion.div>

            <motion.div
              className="relative bg-[#040404] rounded-2xl p-4 z-10"
              animate={{ borderColor: isFocused ? "#BA9465" : "#3D3D3D" }}
              transition={{ duration: 0.6, delay: 0.1 }}
              style={{ borderWidth: "1px", borderStyle: "solid" }}
            >
              <div className="relative mb-6">
                <Textarea
                  placeholder="Ask me anything about your documents..."
                  className="min-h-[80px] resize-none bg-transparent border-none text-white text-base placeholder:text-zinc-500 focus:ring-0 focus:outline-none focus-visible:ring-0 focus-visible:outline-none"
                  value={inputValue}
                  onChange={(e) => setInputValue(e.target.value)}
                  onFocus={() => setIsFocused(true)}
                  onBlur={() => setIsFocused(false)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && !e.shiftKey) {
                      e.preventDefault()
                      handleSendMessage()
                    }
                  }}
                  disabled={isLoading}
                />
              </div>

              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <Button variant="ghost" size="sm" className="h-9 w-9 rounded-full bg-zinc-800 hover:bg-zinc-700 text-zinc-100 hover:text-white p-0">
                    <Brain className="h-4 w-4" />
                  </Button>
                  <Button variant="ghost" size="sm" className="h-9 w-9 rounded-full bg-zinc-800 hover:bg-zinc-700 text-zinc-300 hover:text-white p-0">
                    <Link className="h-4 w-4" />
                  </Button>
                  <div className="flex items-center">
                    <Select defaultValue="gemini-1.5-flash">
                      <SelectTrigger className="bg-zinc-900 border-[#3D3D3D] text-white hover:bg-zinc-700 text-xs rounded-full px-2 h-8 min-w-[150px]">
                        <div className="flex items-center gap-2">
                          <span className="text-xs">⚡</span>
                          <SelectValue />
                        </div>
                      </SelectTrigger>
                      <SelectContent className="bg-zinc-900 z-30 border-[#3D3D3D] rounded-xl">
                        <SelectItem value="gemini-1.5-flash" className="text-white hover:bg-zinc-700 rounded-lg">
                          Gemini 1.5 Flash
                        </SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                </div>

                <div className="flex items-center gap-3">
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-10 w-10 rounded-full bg-orange-500 hover:bg-orange-600 text-white p-0"
                    onClick={handleSendMessage}
                    disabled={isLoading || !inputValue.trim()}
                  >
                    <Send className="h-5 w-5" />
                  </Button>
                </div>
              </div>
            </motion.div>
          </div>
        </div>
      </div>
    </div>
  )
}
