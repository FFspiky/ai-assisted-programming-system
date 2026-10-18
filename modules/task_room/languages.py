"""Local solve(data) adapters. Compilation and execution always stay in Docker.

The small JSON value APIs below cover the complete task catalog, including nested
arrays/objects and Unicode. Expected outputs never enter a user-code process.
"""

import ast
import json
import re

from services.language_support import language_label, language_spec


def normalize_language(value):
    return language_spec(value)["id"]


CPP_HELPER = r"""
#include <algorithm>
#include <cctype>
#include <cmath>
#include <iomanip>
#include <iostream>
#include <iterator>
#include <map>
#include <sstream>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>
using namespace std;
struct Json {
    using Array = vector<Json>; using Object = map<string, Json>;
    enum Kind { Null, Boolean, Integer, Real, Text, List, Dict } kind=Null;
    bool boolean=false; long long integer=0; double real=0;
    string text; Array list; Object object_value;
    Json()=default; Json(nullptr_t) {}
    Json(bool x): kind(Boolean), boolean(x) {} Json(int x): kind(Integer),integer(x) {}
    Json(long long x):kind(Integer),integer(x) {} Json(size_t x):kind(Integer),integer((long long)x) {}
    Json(double x):kind(Real),real(x) {} Json(const char* x):kind(Text),text(x) {}
    Json(string x):kind(Text),text(move(x)) {} Json(Array x):kind(List),list(move(x)) {}
    Json(Object x):kind(Dict),object_value(move(x)) {}
    static Json array() { return Array{}; }
    static Json object() { return Object{}; }
    void require(Kind wanted) const {if(kind!=wanted)throw runtime_error("unexpected JSON type");}
    long long as_int() const {require(Integer);return integer;}
    double as_number() const {if(kind==Integer)return integer;require(Real);return real;}
    string as_string() const {require(Text);return text;}
    bool as_bool() const {require(Boolean);return boolean;}
    const Array& array_items() const {require(List);return list;}
    Array& array_items() {require(List);return list;}
    const Object& object_items() const {require(Dict);return object_value;}
    bool contains(const string& key) const {return kind==Dict && object_value.count(key);}
    size_t size() const {if(kind==List)return list.size();if(kind==Dict)return object_value.size();require(Text);return text.size();}
    Json& operator[](const string& key) {require(Dict);return object_value[key];}
    const Json& operator[](const string& key) const {require(Dict);return object_value.at(key);}
    Json& operator[](size_t i) {require(List);return list.at(i);}
    const Json& operator[](size_t i) const {require(List);return list.at(i);}
    void push_back(Json x) {require(List);list.push_back(move(x));}
    static string quote(const string& s) {
        ostringstream out; out << '"';
        for (unsigned char c : s) { switch(c) {
            case '"': out << "\\\""; break; case '\\': out << "\\\\"; break;
            case '\b': out << "\\b"; break; case '\f': out << "\\f"; break;
            case '\n': out << "\\n"; break; case '\r': out << "\\r"; break; case '\t': out << "\\t"; break;
            default: if(c<32) out << "\\u00" << hex << setw(2) << setfill('0') << (int)c << dec; else out << c;
        }} out << '"'; return out.str();
    }
    string dump() const {
        if(kind==Null) return "null";
        if(kind==Boolean) return boolean?"true":"false";
        if(kind==Integer) return to_string(integer);
        if(kind==Real) { double d=real; if(!isfinite(d)) throw runtime_error("non-finite JSON number"); ostringstream out; out<<setprecision(17)<<d; string s=out.str(); if(s.find_first_of(".eE")==string::npos) s+=".0"; return s; }
        if(kind==Text) return quote(text);
        string s; if(kind==List) { s="["; for(const auto& x: list) {if(s.size()>1)s+=",";s+=x.dump();} return s+"]"; }
        s="{"; for(const auto& p: object_items()){if(s.size()>1)s+=",";s+=quote(p.first)+":"+p.second.dump();}return s+"}";
    }
    struct Parser {
        const string& s; size_t p=0; int depth=0;
        void ws(){while(p<s.size() && isspace((unsigned char)s[p]))++p;}
        char take(){if(p>=s.size())throw runtime_error("unexpected end of JSON");return s[p++];}
        void need(char c){ws();if(take()!=c)throw runtime_error("invalid JSON separator");}
        unsigned hex4(){unsigned n=0;for(int i=0;i<4;i++){char c=take();n*=16;if(c>='0'&&c<='9')n+=c-'0';else if(c>='a'&&c<='f')n+=c-'a'+10;else if(c>='A'&&c<='F')n+=c-'A'+10;else throw runtime_error("invalid unicode escape");}return n;}
        static void utf8(string& out,unsigned n){if(n<128)out+=(char)n;else if(n<2048){out+=(char)(0xc0|(n>>6));out+=(char)(0x80|(n&63));}else if(n<65536){out+=(char)(0xe0|(n>>12));out+=(char)(0x80|((n>>6)&63));out+=(char)(0x80|(n&63));}else{out+=(char)(0xf0|(n>>18));out+=(char)(0x80|((n>>12)&63));out+=(char)(0x80|((n>>6)&63));out+=(char)(0x80|(n&63));}}
        string str(){need('"');string out;for(;;){char c=take();if(c=='"')return out;if((unsigned char)c<32)throw runtime_error("control character");if(c!='\\'){out+=c;continue;}switch(take()){case '"':out+='"';break;case '\\':out+='\\';break;case '/':out+='/';break;case 'b':out+='\b';break;case 'f':out+='\f';break;case 'n':out+='\n';break;case 'r':out+='\r';break;case 't':out+='\t';break;case 'u':{unsigned n=hex4();if(n>=0xd800&&n<=0xdbff){if(take()!='\\'||take()!='u')throw runtime_error("invalid surrogate");unsigned low=hex4();if(low<0xdc00||low>0xdfff)throw runtime_error("invalid surrogate");n=0x10000+((n-0xd800)<<10)+low-0xdc00;}else if(n>=0xdc00&&n<=0xdfff)throw runtime_error("invalid surrogate");utf8(out,n);break;}default:throw runtime_error("invalid escape");}}}
        Json parse(){ws();if(++depth>128)throw runtime_error("JSON too deep");Json out;char c=p<s.size()?s[p]:'\0';
            if(c=='"')out=str();else if(c=='['){++p;Array a;ws();if(p<s.size()&&s[p]==']')++p;else{for(;;){a.push_back(parse());ws();char sep=take();if(sep==']')break;if(sep!=',')throw runtime_error("array separator");}}out=move(a);}
            else if(c=='{'){++p;Object o;ws();if(p<s.size()&&s[p]=='}')++p;else{for(;;){string key=str();need(':');if(o.count(key))throw runtime_error("duplicate key");o[key]=parse();ws();char sep=take();if(sep=='}')break;if(sep!=',')throw runtime_error("object separator");}}out=move(o);}
            else if(s.compare(p,4,"true")==0){p+=4;out=true;}else if(s.compare(p,5,"false")==0){p+=5;out=false;}else if(s.compare(p,4,"null")==0){p+=4;out=nullptr;}
            else{size_t start=p;if(p<s.size()&&s[p]=='-')++p;if(p>=s.size()||!isdigit((unsigned char)s[p]))throw runtime_error("invalid number");if(s[p]=='0')++p;else while(p<s.size()&&isdigit((unsigned char)s[p]))++p;bool real=false;if(p<s.size()&&s[p]=='.'){real=true;++p;size_t q=p;while(p<s.size()&&isdigit((unsigned char)s[p]))++p;if(q==p)throw runtime_error("fraction");}if(p<s.size()&&(s[p]=='e'||s[p]=='E')){real=true;++p;if(p<s.size()&&(s[p]=='+'||s[p]=='-'))++p;size_t q=p;while(p<s.size()&&isdigit((unsigned char)s[p]))++p;if(q==p)throw runtime_error("exponent");}string n=s.substr(start,p-start);out=real?Json(stod(n)):Json(stoll(n));}
            --depth;return out;
        }
    };
    static Json parse(const string& text){Parser p{text};Json out=p.parse();p.ws();if(p.p!=text.size())throw runtime_error("trailing JSON");return out;}
};
"""

CPP_DRIVER = r"""
int main() {
    ios::sync_with_stdio(false);
    string text((istreambuf_iterator<char>(cin)), istreambuf_iterator<char>());
    try {
        Json inputs=Json::parse(text); Json results=Json::array();
        for(size_t i=0;i<inputs.size();++i){
            Json row=Json::object();row["index"]=i;row["actual"]=nullptr;row["error"]=nullptr;
            ostringstream logs; auto* output=cout.rdbuf(logs.rdbuf());auto* errors=cerr.rdbuf(logs.rdbuf());
            try{row["actual"]=solve(inputs[i]);row["actual"].dump();}
            catch(const exception& e){row["error"]=string(e.what()).substr(0,1000);}
            catch(...){row["error"]="unknown exception";}
            cout.rdbuf(output);cerr.rdbuf(errors);results.push_back(row);
        }
        Json packet=Json::object();packet["results"]=results;cout<<packet.dump()<<'\n';
    } catch(const exception& e){cerr<<e.what();return 1;}
}
"""

JAVA_HELPER = r"""
class Json {
    private final Object value;
    private Json(Object value){this.value=value;}
    static Json of(Object value){if(value instanceof Json)return (Json)value;if(value==null||value instanceof String||value instanceof Boolean||value instanceof Number)return new Json(value);throw new IllegalArgumentException("use Json.array/object for containers");}
    static Json object(){return new Json(new java.util.LinkedHashMap<String,Json>());}
    static Json array(){return new Json(new java.util.ArrayList<Json>());}
    @SuppressWarnings("unchecked") java.util.Map<String,Json> objectItems(){return (java.util.Map<String,Json>)value;}
    @SuppressWarnings("unchecked") java.util.List<Json> arrayItems(){return (java.util.List<Json>)value;}
    Json get(String key){Json result=objectItems().get(key);if(result==null)throw new IllegalArgumentException("missing key: "+key);return result;}
    Json get(int index){return arrayItems().get(index);}
    boolean contains(String key){return objectItems().containsKey(key);}
    Json put(String key,Object item){objectItems().put(key,of(item));return this;}
    Json add(Object item){arrayItems().add(of(item));return this;}
    int size(){return value instanceof java.util.Map?objectItems().size():value instanceof java.util.List?arrayItems().size():asString().length();}
    long asInt(){if(!(value instanceof Long||value instanceof Integer))throw new IllegalArgumentException("expected integer");return ((Number)value).longValue();}
    double asNumber(){return ((Number)value).doubleValue();}
    String asString(){return (String)value;}
    boolean asBool(){return (Boolean)value;}
    static String quote(String s){StringBuilder out=new StringBuilder("\"");for(int i=0;i<s.length();i++){char c=s.charAt(i);switch(c){case '"':out.append("\\\"");break;case '\\':out.append("\\\\");break;case '\b':out.append("\\b");break;case '\f':out.append("\\f");break;case '\n':out.append("\\n");break;case '\r':out.append("\\r");break;case '\t':out.append("\\t");break;default:if(c<32)out.append(String.format("\\u%04x",(int)c));else out.append(c);}}return out.append('"').toString();}
    String dump(){if(value==null)return "null";if(value instanceof String)return quote((String)value);if(value instanceof Boolean)return value.toString();if(value instanceof Number){double d=((Number)value).doubleValue();if(!Double.isFinite(d))throw new IllegalArgumentException("non-finite JSON number");return value.toString();}StringBuilder out=new StringBuilder();if(value instanceof java.util.List){out.append('[');for(Json x:arrayItems()){if(out.length()>1)out.append(',');out.append(x.dump());}return out.append(']').toString();}out.append('{');for(java.util.Map.Entry<String,Json> p:objectItems().entrySet()){if(out.length()>1)out.append(',');out.append(quote(p.getKey())).append(':').append(p.getValue().dump());}return out.append('}').toString();}
    static class Parser {
        final String text;int pos=0,depth=0;Parser(String text){this.text=text;}
        void ws(){while(pos<text.length()&&Character.isWhitespace(text.charAt(pos)))pos++;}
        char take(){if(pos>=text.length())throw new IllegalArgumentException("unexpected end of JSON");return text.charAt(pos++);}
        void need(char c){ws();if(take()!=c)throw new IllegalArgumentException("invalid JSON separator");}
        String str(){need('"');StringBuilder out=new StringBuilder();for(;;){char c=take();if(c=='"')return out.toString();if(c<32)throw new IllegalArgumentException("control character");if(c!='\\'){out.append(c);continue;}switch(take()){case '"':out.append('"');break;case '\\':out.append('\\');break;case '/':out.append('/');break;case 'b':out.append('\b');break;case 'f':out.append('\f');break;case 'n':out.append('\n');break;case 'r':out.append('\r');break;case 't':out.append('\t');break;case 'u':String hex="";for(int i=0;i<4;i++)hex+=take();out.append((char)Integer.parseInt(hex,16));break;default:throw new IllegalArgumentException("invalid escape");}}}
        Json read(){ws();if(++depth>128)throw new IllegalArgumentException("JSON too deep");char c=pos<text.length()?text.charAt(pos):0;Json out;
            if(c=='"')out=of(str());else if(c=='['){pos++;out=array();ws();if(pos<text.length()&&text.charAt(pos)==']')pos++;else for(;;){out.add(read());ws();char sep=take();if(sep==']')break;if(sep!=',')throw new IllegalArgumentException("array separator");}}
            else if(c=='{'){pos++;out=object();ws();if(pos<text.length()&&text.charAt(pos)=='}')pos++;else for(;;){String key=str();need(':');if(out.contains(key))throw new IllegalArgumentException("duplicate key");out.put(key,read());ws();char sep=take();if(sep=='}')break;if(sep!=',')throw new IllegalArgumentException("object separator");}}
            else if(text.startsWith("true",pos)){pos+=4;out=of(true);}else if(text.startsWith("false",pos)){pos+=5;out=of(false);}else if(text.startsWith("null",pos)){pos+=4;out=of(null);}
            else{int start=pos;if(pos<text.length()&&text.charAt(pos)=='-')pos++;if(pos>=text.length()||!Character.isDigit(text.charAt(pos)))throw new IllegalArgumentException("invalid number");if(text.charAt(pos)=='0')pos++;else while(pos<text.length()&&Character.isDigit(text.charAt(pos)))pos++;boolean real=false;if(pos<text.length()&&text.charAt(pos)=='.'){real=true;pos++;int q=pos;while(pos<text.length()&&Character.isDigit(text.charAt(pos)))pos++;if(pos==q)throw new IllegalArgumentException("fraction");}if(pos<text.length()&&(text.charAt(pos)=='e'||text.charAt(pos)=='E')){real=true;pos++;if(pos<text.length()&&(text.charAt(pos)=='+'||text.charAt(pos)=='-'))pos++;int q=pos;while(pos<text.length()&&Character.isDigit(text.charAt(pos)))pos++;if(pos==q)throw new IllegalArgumentException("exponent");}String n=text.substring(start,pos);out=real?of(Double.valueOf(n)):of(Long.valueOf(n));}
            depth--;return out;
        }
    }
    static Json parse(String text){Parser p=new Parser(text);Json out=p.read();p.ws();if(p.pos!=text.length())throw new IllegalArgumentException("trailing JSON");return out;}
}
"""

JAVA_DRIVER = r"""
public class Main {
    public static void main(String[] args) throws Exception {
        String text=new String(System.in.readAllBytes(), java.nio.charset.StandardCharsets.UTF_8);
        Json inputs=Json.parse(text),results=Json.array();
        java.io.PrintStream output=System.out,errors=System.err;
        for(int i=0;i<inputs.size();i++){
            Json row=Json.object().put("index",i).put("actual",null).put("error",null);
            java.io.PrintStream logs=new java.io.PrintStream(new java.io.ByteArrayOutputStream(),true,"UTF-8");
            System.setOut(logs);System.setErr(logs);
            try{Json actual=Solution.solve(inputs.get(i));actual.dump();row.put("actual",actual);}
            catch(Throwable e){String message=e.toString();row.put("error",message.substring(0,Math.min(1000,message.length())));}
            finally{System.setOut(output);System.setErr(errors);logs.close();}
            results.add(row);
        }
        output.println(Json.object().put("results",results).dump());
    }
}
"""


def scaffold(scenario, language):
    language = normalize_language(language)
    if language == "python":
        return scenario["starter_code"]
    from .catalog import evaluate_input

    rules = {group["key"]: group["recommended"] for group in scenario["rule_groups"]}
    sample = evaluate_input(scenario["id"], rules, scenario["example_input"])

    def blank(value):
        if isinstance(value, list):
            return "Json::array()" if language == "cpp" else "Json.array()"
        if isinstance(value, dict):
            return "Json::object()" if language == "cpp" else "Json.object()"
        if isinstance(value, bool):
            return "false"
        return '""' if isinstance(value, str) else "0"

    if language == "cpp":
        fields = "".join(
            f"    result[{json.dumps(key, ensure_ascii=False)}] = {blank(value)};\n"
            for key, value in sample.items()
        )
        return (
            f'// {scenario["title"]}: 仅实现 solve，JSON 解析由任务室提供。\n'
            "Json solve(const Json& data) {\n"
            '    // data["字段"].as_int()/as_string()/array_items() 读取输入。\n'
            "    // Json::object()/array() 构造结果；按左侧合同补全业务逻辑。\n"
            "    Json result = Json::object();\n" + fields + "    return result;\n}\n"
        )
    fields = "".join(
        f"        result.put({json.dumps(key, ensure_ascii=False)}, {blank(value)});\n"
        for key, value in sample.items()
    )
    return (
        f'// {scenario["title"]}: JSON 解析由任务室提供，无需 main。\n'
        "class Solution {\n"
        "    static Json solve(Json data) {\n"
        '        // data.get("字段").asInt()/asString()/arrayItems() 读取输入。\n'
        "        // Json.object()/array()，put/add 构造结果。\n"
        "        Json result = Json.object();\n" + fields + "        return result;\n    }\n}\n"
    )


def interface_guide(language):
    language = normalize_language(language)
    if language == "python":
        return (
            "实现 def solve(data)，输入为 dict/list 等 JSON 值，返回约定结果。不要自行读取 stdin。"
        )
    if language == "cpp":
        return (
            "实现 Json solve(const Json& data)，不写 main。已提供 Json 类型："
            'data["key"]、data[index]、as_int()、as_number()、as_string()、as_bool()、'
            "array_items()、object_items()、contains(key)、size()；"
            'Json::object()/array()、result["key"]=value、push_back(value)。可用 C++17 标准库。'
        )
    return (
        "实现非 public class Solution { static Json solve(Json data) { ... } }，不写 main/package/import。"
        "已提供 Json：get(key/index)、asInt()返回long、asNumber()、asString()、asBool()、"
        "arrayItems()、objectItems()、contains(key)、size()；Json.object()/array()、put(key,value)、add(value)。"
        "标准库使用完整包名，例如 java.util.ArrayList。返回 Json，不返回 Map/List。"
    )


def validate_solution(code, language):
    language = normalize_language(language)
    if not isinstance(code, str) or not code.strip() or len(code) > 20000:
        raise ValueError("候选代码须为不超过 20000 字的完整代码。")
    if language == "python":
        tree = ast.parse(code)
        if not any(
            isinstance(node, ast.FunctionDef) and node.name == "solve" for node in tree.body
        ):
            raise ValueError("请定义 solve(data) 函数。")
    else:
        # Structural validation is deliberately not a fake compiler. Docker is
        # the only authority for syntax, runtime and actual acceptance results.
        clean = re.sub(
            r'//[^\n]*|/\*.*?\*/|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'', " ", code, flags=re.S
        )
        if re.search(r"\bmain\s*\(", clean):
            raise ValueError("任务室自动提供 main，请仅提交 solve(data)。")
        if language == "cpp" and not re.search(r"\bJson\s+solve\s*\(\s*const\s+Json\s*&", clean):
            raise ValueError("C++ 请实现 Json solve(const Json& data)。")
        if language == "java" and (
            not re.search(r"\bclass\s+Solution\b", clean)
            or not re.search(r"\bstatic\s+Json\s+solve\s*\(\s*Json\s+", clean)
            or re.search(r"\b(package|import)\b|\bpublic\s+class\b", clean)
        ):
            raise ValueError(
                "Java 请实现非 public 的 class Solution 与 static Json solve(Json data)，无需 package/import。"
            )


def compiled_harness(code, language):
    language = normalize_language(language)
    validate_solution(code, language)
    if language == "cpp":
        return CPP_HELPER + "\n" + code + "\n" + CPP_DRIVER
    if language == "java":
        return JAVA_HELPER + "\n" + code + "\n" + JAVA_DRIVER
    raise ValueError("Python uses the existing isolated harness")


def export_sources(code, language):
    """Exports runnable batch drivers; stdin is an array of JSON test inputs."""
    language = normalize_language(language)
    if language == "cpp":
        return {
            "solution.cpp": code,
            "main.cpp": CPP_HELPER + '\n#include "solution.cpp"\n' + CPP_DRIVER,
        }
    if language == "java":
        return {"Solution.java": code, "Main.java": JAVA_HELPER + JAVA_DRIVER}
    return {
        "solution.py": code,
        "run.py": 'import json, sys\nfrom solution import solve\ninputs = json.load(sys.stdin)\nprint(json.dumps({"results": [{"index": i, "actual": solve(data), "error": None} for i, data in enumerate(inputs)]}, ensure_ascii=False, allow_nan=False))\n',
    }


def source_filename(language):
    return {"python": "solution.py", "cpp": "solution.cpp", "java": "Solution.java"}[
        normalize_language(language)
    ]


def local_instructions(language):
    command = {
        "python": "python run.py < inputs.json",
        "cpp": "g++ -std=c++17 main.cpp -o solution\n./solution < inputs.json",
        "java": "javac -encoding UTF-8 Main.java Solution.java\njava Main < inputs.json",
    }[normalize_language(language)]
    return f"开发语言：{language_label(language)}。{interface_guide(language)}\n\n将导出目录作为工作目录，在可信环境中运行：\n```text\n{command}\n```\nWindows CMD 中 C++ 的启动命令为 solution.exe < inputs.json。inputs.json 为当前合同的输入数组，结果按 inputs 数组顺序输出。"
