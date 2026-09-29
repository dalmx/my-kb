---
title: Main Wongoing.Utility 工具库（加密/Excel/XML/路径）
category: 技术-.NET
module: 通用
factory: 通用
tags: [工具库, WongoingEngine, 加密, Excel, NPOI, XML, Main]
updated: 2026-08-29
status: active
---
# Main Wongoing.Utility 工具库（加密/Excel/XML/路径）

> 框架库 `Frame/Wongoing.Utility/`，命名空间 `Wongoing.Utility.*`。作者孙本强 2013-04-03，多数类沿用至今。跨所有子系统复用。

## 一、WongoingEngine（核心对称加密 —— 系统密码所用）

文件 `Cryptography/WongoingEngine.cs`，命名空间 `Wongoing.Utility.Cryptography`，实现 `ISKCrypto`（对称加密接口）。

### 算法本质：自定义流式 XOR 密码（非 DES/AES）
**不是**标准 DES/AES/RSA，是经典的"**带链式偏移的逐字符异或**"自定义对称算法（俗称 "MIME XOR" 变种）：
- 明文按**字符**(`char`，UTF-16 码元)逐个处理，不是按字节。
- 每个字符先做**模 255 加法**再加偏移，再与**密钥字符循环异或**。
- 输出**十六进制字符串**（每字符对应 2 位 hex）。
- 偏移量**链式传递**：前一字符密文成后一字符偏移。

### 方法签名
```csharp
public string EncryptString(string src, string key, Encoding encoding)
public string DecryptString(string src, string key, Encoding encoding)
```
**关键：`encoding` 参数两方法均未使用**（算法直接操作 `char`，不经字节编码）。传 ASCII/UTF8/Default 结果一样。

### 加密算法（EncryptString）
```text
KeyLen = key.Length;
if (KeyLen == 0) { key = "Wongoing"; }          // ★ 空密钥回退固定默认密钥
KeyPos = 0;
offset = new Random().Next() % 256 + 1;         // 随机初始偏移 1..256
dest = offset 的十六进制(补前导0到2位)           // 密文头2位存偏移
for 每个字符 src[SrcPos]:
    SrcAsc = ((int)src[SrcPos] + offset) % 255; // 步骤1: 模255加法
    if (KeyPos < KeyLen) KeyPos++; else KeyPos = 0;  // 步骤2: 密钥指针前进(先加后用)
    SrcAsc = SrcAsc ^ (int)key[KeyPos];         // 步骤3: 与密钥字符异或
    dest += SrcAsc 的十六进制(补0到2位)          // 步骤4: 拼接密文
    offset = SrcAsc;                            // 步骤5: 偏移链式更新为本次密文
```

### 解密算法（DecryptString，严格逆过程）
```text
if (key.Length == 0) { key = "Wongoing"; }      // 同样默认密钥回退
if (src.Length <= 2) return "";
offset = Convert.ToInt32(src.Substring(0,2), 16);  // 读密文头2位=初始偏移
SrcPos = 2;
while (SrcPos < src.Length):
    SrcAsc = Convert.ToInt32(src.Substring(SrcPos,2), 16);  // 读2位hex=密文值
    if (KeyPos < KeyLen) KeyPos++; else KeyPos = 0;
    TmpSrcAsc = SrcAsc ^ (int)key[KeyPos];      // 逆异或
    if (TmpSrcAsc <= offset) TmpSrcAsc = 255 + TmpSrcAsc - offset;  // 逆模加(处理回绕)
    else TmpSrcAsc = TmpSrcAsc - offset;
    dest += (char)TmpSrcAsc;                    // 还原字符
    offset = SrcAsc;                            // 偏移链式更新(用密文值,与加密一致)
    SrcPos += 2;
```

### 为什么"对称可逆"
加解密用**完全相同的密钥指针推进逻辑**和**相同偏移链**（都用"密文值"作下一轮 offset）。模加的逆运算通过 `if(TmpSrcAsc<=offset)` 分支正确还原回绕。故 `Decrypt(Encrypt(x,k),k) == x`。

### 为什么 `DecryptString(pwd, string.Empty, ASCII)` 空密钥也能解
**核心**：方法内有默认密钥回退——`if (KeyLen == 0) { key = "Wongoing"; }`。传空串触发回退，实际用**固定硬编码密钥 `"Wongoing"`**。所以"空密钥"等于"用 Wongoing 这把固定钥匙"。只要当初加密也用空串（或 "Wongoing"），就能解。

> 🔐 **安全含义（重要）**：系统密码若用此方式加密存储，等于用公开固定密钥加密——任何拿到源码的人都能解，**这不是密码哈希，是可逆加密**。真正的密码存储应用 HashMD5 或加盐哈希。

### 与 HashMd5 的区别
| 维度 | WongoingEngine | HashMD5 |
|------|----------------|---------|
| 接口 | `ISKCrypto`(对称加密) | `IHashCrypto`(哈希) |
| 可逆性 | **可逆**(对称) | **不可逆**(单向) |
| 用途 | 加解密数据(需还原的配置、密码明文还原场景) | 校验/签名(文件完整性、密码哈希存储) |
| 密钥 | 需要(默认 "Wongoing") | 无密钥 |
| 输出 | 变长十六进制串 | ComputeHash 返回 10 位自定义字典串；HashBuff 返回 32 位大写 hex |

### 加密-解密往返示例
```csharp
using Wongoing.Utility.Cryptography;
using System.Text;
var engine = new WongoingEngine();
string plain = "Hello";
string key   = "Wongoing";        // 或传 "" 自动回退到 "Wongoing"
string cipher = engine.EncryptString(plain, key, Encoding.ASCII);  // 形如 "3A1F2C4D..." 每次不同(含随机偏移)
string back = engine.DecryptString(cipher, key, Encoding.ASCII);   // back == "Hello"
```

### 已观察到的潜在缺陷
1. **密钥指针 off-by-one**：`KeyPos` 先自增再取 `key[KeyPos]`，`key[0]` 从不参与异或。用 `"Wongoing"`(长度8) 加密**长度≥8** 字符串时，第 8 个字符使 KeyPos 增到 8，访问 `key[8]` 触发 `IndexOutOfRangeException`。短字符串(≤7)无此问题。生产中用于长文本需留意。
2. **offset=256 越界**：`r.Next()%256+1` 可能产生 256，十六进制是 `"100"`(3位)，但解密固定读前 2 位，导致偏移错位。概率约 1/256。

> 这两点解释了为何系统密码实际多为短串，且偶发"解密失败"。

## 二、ICryptography.cs（加密接口）
- **`ISKCrypto`**（Symmetric Key 对称加密）：`EncryptString`/`DecryptString`
- **`IHashCrypto`**（哈希）：`HashBuff(byte[])`/`HashStream(Stream)`/`HashFile(string)`/`HashString(string,Encoding)`

`WongoingEngine` 实现 `ISKCrypto`；`HashMD5` 实现 `IHashCrypto`。

## 三、HashMD5
文件 `Cryptography/HashMd5.cs`，实现 `IHashCrypto`。
- `ComputeHash(string)` —— **非标准 MD5**：先算 MD5 字节，再用内置字典串 `"ENT2PYQIN3GDARU..."`(92 字符) 做 `byte%92` 映射，截前 10 位。"魔改 MD5"，输出 10 字符短串。
- `HashBuff(byte[])`/`HashStream(Stream)`/`HashFile(path)`/`HashString(str,encoding)` —— 标准 MD5，输出 **32 位大写 hex**。

用途：文件完整性校验、密码哈希存储（不可逆）。

## 四、ExcelDownload（Excel 导出）

文件 `Excel/ExcelDownload.cs`，命名空间 `Wongoing.Utility.Excel`。

### ExcelFileDown
```csharp
public void ExcelFileDown(DataSet ds, string filename)     // 多表
public void ExcelFileDown(DataTable dt, string filename)   // 单表(filename 空→时间戳)
```
流程：①创建 `MemoryStream`；②`new DataToFile().ToExcel(ds, ref ms)` 生成 Excel 写流；③`FileDown` 输出 HttpResponse。

### FileDown（HTTP 输出）
- `HttpContext.Current.Handler` 拿当前 `Page`。
- `Response.Cache.SetCacheability(NoCache)` + `SetNoStore()` 禁缓存。
- `ContentType = "application/octet-stream"`。
- **文件名编码**：`HttpUtility.UrlEncode(filename + ".xlsx", Encoding.UTF8)`，拼 `Content-Disposition: attachment;filename=...`（**输出固定 .xlsx**）。
- `Content-Length` 头 + `BinaryWrite` + `Flush` + `End`。

### 底层库 NPOI（XSSF=.xlsx）
`Excel/DataToExcel.cs` 的 `DataToFile`(partial) 引用 `NPOI.HSSF.UserModel`/`NPOI.XSSF.UserModel`/`NPOI.SS.UserModel`，用 `XSSFWorkbook` 生成 .xlsx。

### 列名与单元格处理
- **WriteTitle**：`DataTable.Columns[i].ColumnName` 作列头(第 0 行)。
- **WriteRow**：按 CLR 类型分支——`DateTime`→`"yyyy-MM-dd HH:mm:ss"` 且 `Replace(" 00:00:00","")`(去零点)；`double`→原值；`decimal`→转 double；`int`→原值；`null`→空串；其它→`ToString()`。
- **分页**：单 Sheet 满 **60000** 行自动建下一 Sheet（命名 `TableName`/`TableName1`/`TableName2`…；表名空用 `"Sheet"`）。

### 读 Excel（FromExcel）
`DataToFile` 提供：
- `FromExcel(string FileName)` → `DataSet`(多表)
- `FromExcel(string FileName, string TableName)` → `DataTable`(按 Sheet 名过滤)
- `FromExcel(Stream stream, string TableName)` → `WorkbookFactory.Create` 自动识别格式
- 公式单元格先 `SetCellType(CellType.String)` 取值
- `_FromExcel` 系列(下划线前缀) 走 **OLEDB(Microsoft.Jet.OLEDB.4.0/Excel 8.0)**，需 x86+AccessDatabaseEngine，一般不用

> 数据导入页 `BaseInfo/Import.aspx.cs` 用 `DataToFile().FromExcel(stream, "Sheet1")` 读 Excel。

## 五、XHelper / XRead（XML 反序列化）

文件 `Xml/XHelper.cs` + `Xml/XRead.cs`，命名空间 `Wongoing.Utility.Xml`。项目自定义轻量 XML→对象映射框架，`dbVersion.config`、McUI 配置均用它解析。

### 入口 XHelper&lt;T&gt;
```csharp
public List<XTarget<T>> DeserializeToTargets(XReader reader)   // 返回实例+原始节点
public List<T> DeserializeToInstances(XReader reader)          // 仅返回实例列表
```
逻辑：①`reader.Node==null && reader.XmlFile!=null` → `new XmlDocument().Load(XmlFile)`；②`reader.TRename`(实体别名) 空 → 取 `typeof(T).Name`；③委托 `new XRead<T>().Read(reader)`。

### XReader（读取参数）
```csharp
public class XReader {
    public string XmlFile { get; set; }   // XML 文件路径
    public XmlNode Node { get; set; }     // 或直接传节点(二选一)
    public string TRename { get; set; }   // 实体类别名(匹配 XML 节点名,默认类名)
}
```

### XTarget&lt;T&gt;（读取结果）
```csharp
public class XTarget<T> {
    public T Instance;        // 映射出的实体
    public XmlNode Node;      // 原始 XML 节点(可二次处理)
    public XReader Reader;
}
```

### 节点→对象映射机制（XRead&lt;T&gt;，核心）
**如何找目标节点**：
- `getClassTNode` 递归遍历，`isClassTXmlNode` 判断节点名是否等于 `TRename`。
- `TRename` 支持**路径式层级匹配**：反斜杠 `\` 分隔，如 `"Root\Item"`，要求节点及祖先链名字依次匹配（从子向父比对）。
- 名称比较**不区分大小写**。

**如何给属性赋值（DeserializeT）**：对每个公共属性 `pi`，按**两个来源**尝试，命中即停：
1. **XmlAttribute 匹配**：遍历节点所有属性，`attribute.Name` 与 `pi.Name` 不区分大小写相等则赋值。
2. **XmlNode 子节点匹配**：遍历子节点 `piNode`——
   - `piNode.HasChildNodes && piNode.Name==pi.Name`：取 `piNode.FirstChild.Value`(文本节点值)赋值。
   - `piNode` 无子节点但有属性：找名为 `"value"` 的属性且 `piNode.Name==pi.Name` 时赋该属性值（支持 `<PropName value="xxx"/>` 写法）。

**类型转换（changeType）**：支持枚举、`Nullable<T>`、`Guid`、`Version`、`IConvertible`；基本类型/字符串走 `getPrimitiveTypeValue`。`setValue` 包 try/catch，**异常吞掉不抛**。

**是否支持嵌套**：当前**只做单层平铺映射**（属性名↔同名子节点或同名属性），不递归到复杂对象属性；但可通过 `TRename` 路径语法 + 多次调用分层解析。

### 用法示例
```csharp
var reader = new XReader { XmlFile = "dbVersion.config" };
List<DbSource> list = new XHelper<DbSource>().DeserializeToInstances(reader);
```

## 六、Path / FilePath 工具

文件 `FilePath/Path.cs`，命名空间 `Wongoing.Utility.FilePath`。

### Path.AppDirectory()
```csharp
public DirectoryInfo AppDirectory()
```
- **优先**返回 `HttpContext.Current.Request.PhysicalApplicationPath`（**网站根目录物理路径**，不是 bin）。
- 无 HttpContext(非 Web) 回退 `System.Environment.CurrentDirectory`。

### FileClass（文件操作）
| 方法 | 作用 |
|------|------|
| `UploadFiles(uploadFolder, serverName)` | 多文件上传，返回"相对路径,"拼接串 |
| `FiFileExists`/`FiFileDel` | 判断存在/删除 |
| `FiResponseFile(filepath, filename, filetype)` | 10KB 分块向 Response 输出大文件，支持断连检测 |
| `BackupFile`/`RestoreFile` | 文件备份/恢复(恢复前可二次备份) |
| `GetFileExtName` | 取小写扩展名 |
| `GetRootUrl(forumPath)` | 拼站点根 URL(含端口,80 省略) |
| `ImIsImgFilename`/`ImIsZipFilename` | 判断图片/压缩包 |
| `CreateFolder`/`CreateFile`/`DeleteFile` | 目录/文件创建删除 |
| `SaveFile(uploadPath, HttpPostedFile)` | 按时间戳+随机数命名保存上传文件 |

### Utils_Encode / Utils_String
- 编码：`EnHtmlEncode/Decode`、`EnUrlEncode/Decode`、`EnFindNoUTF8File`(找非 UTF8 的 .htm)。
- 字符串（内容多）：`GetStringLength`(汉字算2)、`IsCompriseStr`、`StrIsNullOrEmpty`、`InArray`(多重载)、`RTrim`、`SQLImmitWhile`(简单 SQL 关键字过滤)、`ClearBR`、`CutString`/`GetSubString`/`GetUnicodeSubString`(按字节截断,区分中日韩)、`ReplaceString`、`IsSafeSqlString`、`SplitString`(多重载,支持去重/长度约束)、`DistinctStringArray`、`PadStringArray`、`EncodeHtml`、`StrFilter`(脏字过滤)、`HtmlEncode/Decode`、`UrlEncode/Decode`、`GetTruePath`、`RemoveHtml`/`RemoveUnsafeHtml`/`GetTextFromHTML`、`ClearLastChar`、`MergeString`、`ToSChinese`/`ToTChinese`(简繁转换,用 Microsoft.VisualBasic)、日期系列 `GetDate/GetTime/GetDateTime/GetDateTimeDetail/GetStandardDateTime`。

## 七、Collections 扩展

### DicFactory&lt;TValue&gt;
```csharp
public class DicFactory<TValue> {
    public Dictionary<string, TValue> New() {
        return new Dictionary<string, TValue>(StringComparer.OrdinalIgnoreCase);
    }
}
```
工厂：创建**键忽略大小写**的 `Dictionary<string,TValue>`。用法 `new DicFactory<int>().New()`。

### DistinctExtensions（lambda 去重）
```csharp
public static IEnumerable<T> Distinct<T, V>(this IEnumerable<T> source, Func<T, V> keySelector)
```
扩展方法，按**指定键**去重（`CommonEqualityComparer<T,V>`，用 `EqualityComparer<V>.Default`）。用法 `list.Distinct(x => x.Id)`。

## 八、DNDDS / DNDDSToCDS（Delphi ClientDataset 互转）
文件 `DNDDS/DNDDSToCDS.cs`，命名空间 `Wongoing.Utility.DNDDS`。
**用途**：.NET `DataTable` 与 **Delphi ClientDataset(CDS) XML 格式**双向转换——系统历史上有与 Delphi 客户端/老系统交互需求。

### DataTable → CDS XML
`DataTableToXmlString(DataTable)` / `(DataTable, string[,] defaultValue)` 生成 Delphi CDS 风格：
- `<DATAPACKET><METADATA><FIELDS>...</FIELDS><PARAMS/></METADATA><ROWDATA><ROW .../></ROWDATA></DATAPACKET>`
- **字段类型映射**(.NET→CDS fieldtype)：boolean→boolean；byte/int16→i2；int32→i4；int64→i8；datetime→dateTime；double/single→r8；decimal→fixed(DECIMALS=4,WIDTH=19)；guid→string SUBTYPE=Guid；string→string(超8000→bin.hex Text)；byte[]→bin.hex Binary。只读加 `readonly="true"`；自增列加 `SUBTYPE="Autoinc"`。
- **行数据**：每行一个 `<ROW>` 列为属性；`byte[]` Base64；`datetime`→`yyyyMMddTHHmmssfff`；`>`/`"` XML 实体转义；跳过 Deleted 行。

### CDS XML → DataTable
`XmlStringToDataTable(string, ref DataTable)`：`XmlTextReader` 流式读，识别 `<PARAMS>`(取 Change_Log) 和 `<ROW>`(属性映射列,RowState 标记行状态)。
- **行状态码**：2=删除、4=新增、8=修改、10=修改后删除、12=新增后修改。
- `Buf_FindOrgNo` 递归定位"修改行"原始行号，处理多步变更链。
- 支持类型化解析（boolean/数值/datetime/字符串截断/byte[] Base64）。

> 遗留 Delphi 互操作专用，新功能一般不用。

## 九、整体结论与使用建议
1. **系统密码**：WongoingEngine 用空密钥(实际 "Wongoing")加解密 = **可逆弱加密**，不适合密码存储；推荐 `HashMD5.HashString` 不可逆哈希。`encoding` 参数是摆设。
2. **Excel 导出**：统一 `ExcelDownload.ExcelFileDown`，底层 NPOI XSSF(.xlsx)，列名取 DataTable 列名，文件名 UTF8 UrlEncode，60000 行自动分 Sheet。
3. **配置解析**：`XHelper<T>`+`XReader` 是项目 XML→对象标准方式，属性名与 XML 同名属性/同名子节点(或 `<X value="..."/>`)匹配，名称不区分大小写。
4. **路径**：`Path.AppDirectory()` 返回**网站根目录**(非 bin)。

## 十、反向链接
- `main-auth-and-login.md` — WongoingEngine 在登录密码中的应用
- `main-business-pages.md` — MyUser 改密码用 WongoingEngine
- `main-multi-dbversion-datasource.md` — dbVersion.config 用 XHelper 解析
- `main-mcui-config-framework.md` — McUI XML 用 XHelper 解析
- `main-data-access-internals.md` — SqlMap.config 密码用 WongoingEngine 解密
- `openpyxl-xlsx-compat-fix.md`— Excel 兼容性